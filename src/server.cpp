#include "lac/server.hpp"
#include "lac/integrations.hpp"
#include <arpa/inet.h>
#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <netinet/in.h>
#include <poll.h>
#include <sstream>
#include <stdexcept>
#include <sys/socket.h>
#include <unistd.h>

namespace lac {
namespace {
volatile std::sig_atomic_t stop_requested=0;
void on_signal(int){stop_requested=1;}
std::string trim(const std::string& x) {
  const auto a=x.find_first_not_of(" \t\r\n");
  if(a==std::string::npos)return "";
  const auto b=x.find_last_not_of(" \t\r\n");return x.substr(a,b-a+1);
}
std::string lower(std::string x){
  std::transform(x.begin(),x.end(),x.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
  return x;
}
std::string decode(const std::string& x){
  std::string out;
  for(size_t i=0;i<x.size();++i){
    if(x[i]=='%'&&i+2<x.size()){
      auto hex=[](char c)->int{if(c>='0'&&c<='9')return c-'0';
        if(c>='a'&&c<='f')return c-'a'+10;
        if(c>='A'&&c<='F')return c-'A'+10;
        return -1;};
      const int hi=hex(x[i+1]),lo=hex(x[i+2]);
      if(hi>=0&&lo>=0){const char c=static_cast<char>(hi*16+lo);
        if(c=='\0')throw std::runtime_error("NUL byte not allowed");
        out+=c;i+=2;continue;}
    }
    out+= x[i]=='+'?' ':x[i];
  }
  return out;
}
std::map<std::string,std::string> parameters(const std::string& s){
  std::map<std::string,std::string> q;
  size_t start=0;
  while(start<s.size()){
    const auto end=s.find('&',start);
    const auto entry=s.substr(start,end==std::string::npos?std::string::npos:end-start);
    const auto eq=entry.find('=');
    if(eq!=std::string::npos)q[decode(entry.substr(0,eq))]=decode(entry.substr(eq+1));
    if(end==std::string::npos)break;
    start=end+1;
  }
  return q;
}
std::string value(const std::map<std::string,std::string>& q,const std::string& name){
  auto i=q.find(name);return i==q.end()?"":i->second;
}
std::string read_file(const fs::path& path){
  std::ifstream f(path,std::ios::binary);
  if(!f)throw std::runtime_error("web asset not found: "+path.string());
  std::ostringstream os;os<<f.rdbuf();return os.str();
}
void send_all(int fd,const std::string& text){
  size_t pos=0;
  while(pos<text.size()){
    const ssize_t n=::send(fd,text.data()+pos,text.size()-pos,MSG_NOSIGNAL);
    if(n<=0){if(n<0&&errno==EINTR)continue;break;}
    pos+=static_cast<size_t>(n);
  }
}
void respond(int fd,int status,const std::string& content_type,const std::string& body,const std::string& cookie=""){
  const std::string status_text=status==200?"OK":status==201?"Created":status==400?"Bad Request":
    status==401?"Unauthorized":status==403?"Forbidden":status==404?"Not Found":status==405?"Method Not Allowed":
    status==429?"Too Many Requests":status==503?"Service Unavailable":
    status==413?"Payload Too Large":"Internal Server Error";
  std::ostringstream headers;
  headers<<"HTTP/1.1 "<<status<<" "<<status_text<<"\r\n"
    <<"Content-Type: "<<content_type<<"\r\n"
    <<"Content-Length: "<<body.size()<<"\r\n"
    <<"Cache-Control: no-store\r\n"
    <<"X-Content-Type-Options: nosniff\r\n"
    <<"X-Frame-Options: DENY\r\n"
    <<"Referrer-Policy: no-referrer\r\n"
    <<"Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; "
         "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'\r\n";
  if(!cookie.empty())headers<<"Set-Cookie: "<<cookie<<"\r\n";
  headers<<"Connection: close\r\n\r\n";
  send_all(fd,headers.str()+body);
}
void json_error(int fd,int status,const std::string& message){
  respond(fd,status,"application/json; charset=utf-8","{\"error\":"+json_string(message)+"}");
}
std::string encode(const std::string& input){
  const char* hex="0123456789ABCDEF";std::string out;
  for(unsigned char c:input){
    if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_'||c=='.')out+=static_cast<char>(c);
    else{out+='%';out+=hex[c>>4];out+=hex[c&15];}
  }
  return out;
}
std::string session_token(const std::map<std::string,std::string>& headers){
  const auto bearer=value(headers,"authorization");
  if(!bearer.empty())return bearer.starts_with("Bearer ")?bearer.substr(7):"";
  std::istringstream cookies(value(headers,"cookie"));std::string part,token;int count=0;
  while(std::getline(cookies,part,';')){
    part=trim(part);if(part.starts_with("lac_session=")){token=part.substr(12);++count;}
  }
  return count==1?token:"";
}
struct AuthReply{int status;std::string body,cookie;};
AuthReply authenticate(Sqlite& db,const fs::path& helper,const std::string& action,const std::string& params) try {
  const char* filename=sqlite3_db_filename(db.db,"main");
  if(!filename)throw std::runtime_error("authentication database path unavailable");
  const auto raw=integration_request(helper,std::string(filename)+".auth.sqlite3",action,params,true);
  sqlite3_stmt* statement=nullptr;
  if(sqlite3_prepare_v2(db.db,"SELECT json_extract(?1,'$.status'),json_extract(?1,'$.body'),COALESCE(json_extract(?1,'$.cookie'),'')",-1,&statement,nullptr)!=SQLITE_OK)
    throw std::runtime_error("authentication response unavailable");
  sqlite3_bind_text(statement,1,raw.c_str(),-1,SQLITE_TRANSIENT);
  if(sqlite3_step(statement)!=SQLITE_ROW||sqlite3_column_type(statement,1)==SQLITE_NULL){
    sqlite3_finalize(statement);throw std::runtime_error("invalid authentication response");
  }
  AuthReply result{sqlite3_column_int(statement,0),reinterpret_cast<const char*>(sqlite3_column_text(statement,1)),
                   reinterpret_cast<const char*>(sqlite3_column_text(statement,2))};
  sqlite3_finalize(statement);
  if(result.status<200||result.status>599||result.cookie.find_first_of("\r\n")!=std::string::npos)
    throw std::runtime_error("invalid authentication response");
  return result;
}catch(const std::exception&){
  return {503,"{\"error\":\"Autenticação indisponível. Contate o administrador.\"}",""};
}
void handle_client(int fd,Sqlite& db,int port,const fs::path& web_root,
                   const fs::path& integration_helper,const fs::path& integration_config,
                   bool network) {
  timeval timeout{4,0};
  setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
  setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
  std::string buffer;
  std::array<char,8192> chunk{};
  size_t header_end=std::string::npos;
  while((header_end=buffer.find("\r\n\r\n"))==std::string::npos){
    const ssize_t n=recv(fd,chunk.data(),chunk.size(),0);
    if(n<=0) return;
    buffer.append(chunk.data(),static_cast<size_t>(n));
    if(buffer.size()>8192){json_error(fd,413,"headers exceed 8KiB");return;}
  }
  const std::string header=buffer.substr(0,header_end);
  std::istringstream head(header);std::string request_line;
  std::getline(head,request_line);
  std::istringstream first(trim(request_line));
  std::string method,target,http_version,extra;
  first>>method>>target>>http_version>>extra;
  if((method!="GET"&&method!="POST")||target.empty()||target.size()>4096||
     http_version!="HTTP/1.1"||!extra.empty()){
    json_error(fd,405,"unsupported HTTP request");return;
  }
  std::map<std::string,std::string> headers;
  std::string line;
  while(std::getline(head,line)){
    line=trim(line);if(line.empty())continue;
    const auto colon=line.find(':');
    if(colon==std::string::npos){json_error(fd,400,"invalid HTTP header");return;}
    const std::string key=lower(trim(line.substr(0,colon)));
    if(headers.contains(key)){json_error(fd,400,"duplicate header forbidden");return;}
    headers[key]=trim(line.substr(colon+1));
  }
  const auto host=value(headers,"host");
  const auto local_ip="127.0.0.1:"+std::to_string(port);
  const auto local_name="localhost:"+std::to_string(port);
  bool valid_host=host==local_ip||host==local_name;
  if(network){
    const auto colon=host.rfind(':');
    const auto hostname=host.substr(0,colon);in_addr parsed{};
    valid_host=valid_host||(colon!=std::string::npos&&host.substr(colon+1)==std::to_string(port)
                         &&inet_pton(AF_INET,hostname.c_str(),&parsed)==1);
  }
  if(!valid_host){json_error(fd,403,"invalid host; use an IPv4 address or localhost");return;}
  const auto origin=value(headers,"origin");
  const char* cookie_secure=std::getenv("LAC_COOKIE_SECURE");
  const bool https_origin=cookie_secure&&std::string(cookie_secure)=="1"&&origin=="https://"+host;
  if(!origin.empty() && origin!="http://"+host&&!https_origin){
    json_error(fd,403,"cross-origin operation not allowed");return;
  }
  const auto question=target.find('?');
  const std::string path=target.substr(0,question);
  std::string param_str=question==std::string::npos?"":target.substr(question+1);
  if(method=="POST") {
    if(value(headers,"x-lac-local")!="1") {json_error(fd,403,"missing local API header");return;}
    if(value(headers,"content-type")!="application/x-www-form-urlencoded"){
      json_error(fd,400,"Content-Type must be application/x-www-form-urlencoded");return;
    }
    const auto length=value(headers,"content-length");
    size_t bytes=0;
    try {bytes=std::stoul(length);if(length!=std::to_string(bytes))throw std::runtime_error("bad");}
    catch(...){json_error(fd,400,"Content-Length required");return;}
    if(bytes>16384){json_error(fd,413,"body exceeds 16KiB");return;}
    std::string body=buffer.substr(header_end+4);
    if(body.size()>bytes){json_error(fd,400,"ambiguous request body");return;}
    while(body.size()<bytes){
      const ssize_t n=recv(fd,chunk.data(),std::min(chunk.size(),bytes-body.size()),0);
      if(n<=0){json_error(fd,400,"truncated request body");return;}
      body.append(chunk.data(),static_cast<size_t>(n));
    }
    param_str=body;
  }
  std::map<std::string,std::string> q;
  try {q=parameters(param_str);} catch(const std::exception& e){json_error(fd,400,e.what());return;}
  try {
    std::string output,content_type="application/json; charset=utf-8";int status=200;
    const auto auth_helper=integration_helper.parent_path()/"lac_auth.py";
    const auto auth_token="token="+encode(session_token(headers));
    if(method=="GET"&&path=="/api/auth/status"){
      const auto reply=authenticate(db,auth_helper,"status",auth_token);
      respond(fd,reply.status,content_type,reply.body,reply.cookie);return;
    }
    if(method=="POST"&&(path=="/api/auth/request-code"||path=="/api/auth/verify-code"||path=="/api/auth/logout")){
      sockaddr_in peer{};socklen_t size=sizeof(peer);char ip[INET_ADDRSTRLEN]{};
      if(getpeername(fd,reinterpret_cast<sockaddr*>(&peer),&size)==0)inet_ntop(AF_INET,&peer.sin_addr,ip,sizeof(ip));
      const auto params=auth_token+"&email="+encode(value(q,"email"))+"&code="+encode(value(q,"code"))+"&ip="+encode(ip);
      const auto action=path.substr(std::string("/api/auth/").size());
      const auto reply=authenticate(db,auth_helper,action,params);
      respond(fd,reply.status,content_type,reply.body,reply.cookie);return;
    }
    if(path.starts_with("/api/")&&!(method=="GET"&&path=="/api/health")){
      const auto reply=authenticate(db,auth_helper,"authorize",auth_token);
      if(reply.status!=200){respond(fd,reply.status,content_type,reply.body);return;}
    }
    const bool llm=value(headers,"x-lac-agent")=="mcp";
    if(method=="GET"){
      if(path=="/"||path=="/index.html"){
        output=read_file(web_root/"index.html");content_type="text/html; charset=utf-8";
      }else if(path=="/app.js"){
        output=read_file(web_root/"app.js");content_type="text/javascript; charset=utf-8";
      }else if(path=="/style.css"){
        output=read_file(web_root/"style.css");content_type="text/css; charset=utf-8";
      }else if(path=="/favicon.svg"){
        output=read_file(web_root/"favicon.svg");content_type="image/svg+xml";
      }else if(path=="/assets/lac-symbol.svg"){
        output=read_file(web_root/"assets"/"lac-symbol.svg");content_type="image/svg+xml";
      }else if(path=="/assets/lac-icon-512.png"){
        output=read_file(web_root/"assets"/"lac-icon-512.png");content_type="image/png";
      }else if(path=="/api/health")output="{\"ok\":true,\"service\":\"lac\",\"mode\":\"local\",\"version\":\"0.1.4\",\"auth_required\":true,\"mcp\":\"stdio_bridge\"}";
      else if(path=="/api/integrations"||path=="/api/integrations/recoll/search"||path=="/api/integrations/activitywatch/activity"){
        const std::string action=path=="/api/integrations"?"status":path=="/api/integrations/recoll/search"?"search":"activity";
        output=integration_request(integration_helper,integration_config,action,param_str);
        if(output.starts_with("{\"error\":"))status=400;
      }
      else if(path=="/api/verify"){
        std::string message;
        const bool ok=verify_chain(db,message);
        output="{\"ok\":"+std::string(ok?"true":"false")+",\"message\":"+json_string(message)+"}";
      }
      else if(path=="/api/stats")output=json_stats(db);
      else if(path=="/api/report"){
        output=markdown_report(db,q);content_type="text/markdown; charset=utf-8";
      }
      else if(path=="/api/events")output=json_events(db,q);
      else if(path=="/api/projects")output=json_projects(db);
      else if(path=="/api/roots")output=json_roots(db);
      else if(path=="/api/relations")output=json_relations(db);
      else if(path=="/api/todos")output=json_todos(db);
      else if(path=="/api/assistant/insights")output=json_continuity_insights(db, value(q,"project"));
      else if(path=="/api/assistant/jobs")output=json_continuity_jobs(db);
      else if(path=="/api/assistant/feedback")output=json_continuity_feedback(db, value(q,"project"));
      else if(path=="/api/documents")output=json_documents(db, q);
      else if(path=="/api/documents/read"){
        std::string authorized_roots;
        for(const auto& r: roots(db)){
          if(!authorized_roots.empty()) authorized_roots += "|";
          authorized_roots += r.path;
        }
        const std::string params = param_str + "&roots=" + encode(authorized_roots);
        output=integration_request(integration_helper,integration_config,"read_document",params);
        if(output.starts_with("{\"error\":"))status=400;
      }
      else {json_error(fd,404,"route not found");return;}
    } else {
      if(path=="/api/integrations/configure"){
        output=integration_request(integration_helper,integration_config,"configure",param_str);
        if(output.starts_with("{\"error\":"))status=400;
      }else if(path=="/api/roots"){
        const int id=register_root(db,value(q,"project"),value(q,"path"),value(q,"kind"));
        output="{\"id\":"+std::to_string(id)+"}";status=201;
      }else if(path=="/api/scan"){
        const int changes=scan_all(db);
        output="{\"new_events\":"+std::to_string(changes)+"}";
      }else if(path=="/api/notes"){
        const auto id=record_note(db,value(q,"project"),value(q,"kind"),value(q,"title"),
                                  value(q,"body"),value(q,"reference"),llm);
        output="{\"id\":"+std::to_string(id)+"}";status=201;
      }else if(path=="/api/todos/close"){
        const auto id=close_todo(db,std::stoll(value(q,"id")),llm);
        output="{\"id\":"+std::to_string(id)+"}";status=201;
      }else if(path=="/api/relations"){
        const auto id=record_relation(db,value(q,"from"),value(q,"to"),value(q,"label"),value(q,"state"),llm);
        output="{\"id\":"+std::to_string(id)+"}";status=201;
      }else if(path=="/api/assistant/feedback"){
        int64_t ins_id = 0;
        try { if(!value(q,"insight_id").empty()) ins_id = std::stoll(value(q,"insight_id")); } catch(...) {}
        const auto id=record_feedback(db, ins_id, value(q,"project"), value(q,"target_type"),
                                      value(q,"target_ref"), value(q,"decision"), value(q,"reason"),
                                      llm ? "llm" : "user");
        output="{\"id\":"+std::to_string(id)+"}";status=201;
      }else {json_error(fd,404,"route not found");return;}
    }
    respond(fd,status,content_type,output);
  }catch(const std::exception& ex){
    std::cerr<<"request error: "<<ex.what()<<"\n";
    std::string err_msg = "request failed; see local server log";
    std::string what = ex.what();
    if(what == "root path must be an existing directory") {
      err_msg = "O caminho informado não existe ou não é um diretório acessível no servidor LAC.";
    } else if(what == "path already belongs to a different project") {
      err_msg = "Este caminho já está cadastrado em outro projeto.";
    } else if(what == "kind must be git or docs") {
      err_msg = "Tipo inválido: selecione git ou docs.";
    } else if(what == "todo already closed") {
      err_msg = "Esta pendência já foi concluída anteriormente.";
    } else if(what.find("SQL") == std::string::npos && what.find("syntax") == std::string::npos && what.size() < 120) {
      err_msg = what;
    }
    json_error(fd,path.starts_with("/api/auth/")?503:400, err_msg);
  }
}
} // namespace
void serve(Sqlite& db,int port,int scan_every,const fs::path& web_root,
           const fs::path& integration_helper,const fs::path& integration_config,
           const std::string& bind_address,const std::string& token){
  if(port<1024||port>65535)throw std::runtime_error("port must be 1024-65535");
  if(scan_every<0||scan_every>86400)throw std::runtime_error("scan interval must be 0-86400 seconds");
  const bool network=bind_address!="127.0.0.1";
  if(!token.empty()&&token.size()<32)throw std::runtime_error("LAC_SERVICE_TOKEN must have at least 32 characters");
  if(token.find_first_of("\r\n")!=std::string::npos)throw std::runtime_error("invalid API token");
  if(!fs::is_regular_file(web_root/"index.html"))throw std::runtime_error("web UI assets missing: "+web_root.string());
  const int listener=socket(AF_INET,SOCK_STREAM|SOCK_CLOEXEC,0);
  if(listener<0)throw std::runtime_error("socket failed");
  int reuse=1;setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
  sockaddr_in address{};address.sin_family=AF_INET;
  if(inet_pton(AF_INET,bind_address.c_str(),&address.sin_addr)!=1){close(listener);throw std::runtime_error("--bind requires an IPv4 address");}
  address.sin_port=htons(static_cast<uint16_t>(port));
  if(bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0||listen(listener,16)<0){
    close(listener);throw std::runtime_error("cannot bind to "+bind_address+":"+std::to_string(port));
  }
  auto old_int=std::signal(SIGINT,on_signal);
  auto old_term=std::signal(SIGTERM,on_signal);
  std::cout<<"LAC: http://"<<bind_address<<":"<<port<<" (API; MCP opcional)\n"<<std::flush;
  auto next_scan=std::chrono::steady_clock::now();
  while(!stop_requested){
    if(scan_every>0&&std::chrono::steady_clock::now()>=next_scan){
      try{const auto n=scan_all(db);if(n)std::cout<<"observados: "<<n<<" novos eventos\n"<<std::flush;}
      catch(const std::exception& e){std::cerr<<"scan failed: "<<e.what()<<"\n";}
      next_scan=std::chrono::steady_clock::now()+std::chrono::seconds(scan_every);
    }
    pollfd pfd{listener,POLLIN,0};
    const int n=poll(&pfd,1,500);
    if(n>0&&(pfd.revents&POLLIN)){
      int client=accept4(listener,nullptr,nullptr,SOCK_CLOEXEC);
      if(client>=0){handle_client(client,db,port,web_root,integration_helper,integration_config,network);close(client);}
    }else if(n<0&&errno!=EINTR)break;
  }
  close(listener);std::signal(SIGINT,old_int);std::signal(SIGTERM,old_term);
}
} // namespace lac
