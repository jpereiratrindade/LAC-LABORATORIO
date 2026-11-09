#include "lac/core.hpp"
#include "lac/server.hpp"
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <sys/stat.h>
#include <map>
#include <stdexcept>
#include <string>

namespace {
using lac::fs::path;
std::string option(const std::map<std::string,std::string>& args,const std::string& key,const std::string& fallback=""){
  auto it=args.find(key);return it==args.end()?fallback:it->second;
}
std::map<std::string,std::string> arguments(int argc,char** argv,int begin){
  std::map<std::string,std::string> out;
  for(int i=begin;i<argc;++i){
    const std::string key=argv[i];
    if(!key.starts_with("--")||i+1>=argc)throw std::runtime_error("expected --key value arguments");
    if(out.contains(key))throw std::runtime_error("duplicate option: "+key);
    out[key]=argv[++i];
  }
  return out;
}
void help(){
  std::cout<<R"(LAC - Laboratorio de Continuidade v0.1.4
Uso:
  lac init [--db CAMINHO]
  lac register --project NOME --path DIRETORIO --kind git|docs [--db CAMINHO]
  lac scan [--db CAMINHO]
  lac verify [--db CAMINHO] [--anchor ARQUIVO]
  lac anchor --out CAMINHO [--db CAMINHO]
  lac report --from AAAA-MM-DD --to AAAA-MM-DD --out RELATORIO.md [--db CAMINHO]
  lac stats [--db CAMINHO]
  lac serve [--db CAMINHO] [--port 8765] [--scan-every 180] [--webroot WEB]
            [--bind 127.0.0.1|0.0.0.0] [--integration-helper SCRIPT] [--integration-config ARQUIVO]

API restrita por padrao: login por codigo enviado ao e-mail @embrapa.br.
Rede local: --bind 0.0.0.0. Configure LAC_SMTP_* para envio de codigos.
MCP opcional: python3 scripts/lac_mcp.py [--url http://127.0.0.1:8765] [--allow-write]

Banco padrao: ~/.local/share/lac/lac.db (ou $XDG_DATA_HOME/lac/lac.db)
Os diretorios precisam ser registrados explicitamente; nenhuma observacao automatica do home.
Os textos escritos manualmente sao declaracoes, nunca evidencias cientificas verificadas.
)";
}
path database_path(const std::map<std::string,std::string>& a){
  if(a.contains("--db"))return a.at("--db");
  if(const char* xdg=std::getenv("XDG_DATA_HOME");xdg&&*xdg)return path(xdg)/"lac"/"lac.db";
  if(const char* home=std::getenv("HOME");home&&*home)return path(home)/".local"/"share"/"lac"/"lac.db";
  throw std::runtime_error("--db required when HOME is unavailable");
}
path web_root(const std::map<std::string,std::string>& a,const path& executable){
  if(a.contains("--webroot"))return a.at("--webroot");
  const auto near_binary=lac::fs::weakly_canonical(executable).parent_path();
  for(const auto& candidate:{lac::fs::current_path()/"web",near_binary/"../web",near_binary/"../share/lac/web"}){
    if(lac::fs::is_regular_file(candidate/"index.html"))return candidate;
  }
  throw std::runtime_error("web files not found, set --webroot ./web");
}
path integration_helper(const std::map<std::string,std::string>& a,const path& executable){
  if(a.contains("--integration-helper"))return a.at("--integration-helper");
  const auto near_binary=lac::fs::weakly_canonical(executable).parent_path();
  for(const auto& candidate:{near_binary/"../scripts/lac_integrations.py",
                            near_binary/"../share/lac/scripts/lac_integrations.py"}){
    if(lac::fs::is_regular_file(candidate))return lac::fs::weakly_canonical(candidate);
  }
  return near_binary/"../share/lac/scripts/lac_integrations.py";
}
}
int main(int argc,char** argv){
  try{
    if(argc<2||std::string(argv[1])=="help"||std::string(argv[1])=="--help"){help();return 0;}
    umask(0077);
    const std::string cmd=argv[1];
    const auto args=arguments(argc,argv,2);
    const auto file=database_path(args);
    lac::Sqlite db(file);lac::initialize(db);
    if(cmd=="init"){
      std::cout<<"LAC initialized: "<<file<<"\n";
    }else if(cmd=="register"){
      const auto id=lac::register_root(db,option(args,"--project"),option(args,"--path"),option(args,"--kind"));
      std::cout<<"registered root id="<<id<<"\n";
    }else if(cmd=="scan"){
      const int n=lac::scan_all(db);std::cout<<"new events: "<<n<<"\n";
    }else if(cmd=="verify"){
      std::string message;const bool ok=lac::verify_chain(db,message);
      if(ok && args.contains("--anchor")){
        std::string anchored;const bool anchor_ok=lac::verify_anchor(db,args.at("--anchor"),anchored);
        message+="; "+anchored;
        std::cout<<message<<"\n";return anchor_ok?0:2;
      }
      std::cout<<message<<"\n";return ok?0:2;
    }else if(cmd=="anchor"){
      if(!args.contains("--out"))throw std::runtime_error("--out required");
      lac::write_anchor(db,args.at("--out"));std::cout<<"anchor created: "<<args.at("--out")<<"\n";
    }else if(cmd=="report"){
      if(!args.contains("--out"))throw std::runtime_error("--out required");
      std::ofstream report_file(args.at("--out"),std::ios::binary|std::ios::trunc);
      if(!report_file)throw std::runtime_error("cannot write report");
      report_file<<lac::markdown_report(db,{{"from",option(args,"--from")},
                                     {"to",option(args,"--to")}});
      if(!report_file)throw std::runtime_error("report write failed");
      std::cout<<"report: "<<args.at("--out")<<"\n";
    }else if(cmd=="stats"){
      std::cout<<lac::json_stats(db)<<"\n";
    }else if(cmd=="serve"){
      const int port=std::stoi(option(args,"--port","8765"));
      const int seconds=std::stoi(option(args,"--scan-every","180"));
      const char* token=std::getenv("LAC_SERVICE_TOKEN");
      lac::serve(db,port,seconds,web_root(args,argv[0]),integration_helper(args,argv[0]),
                 option(args,"--integration-config",file.string()+".integrations.json"),
                 option(args,"--bind","127.0.0.1"),token?token:"");
    }else {help();return 2;}
    return 0;
  }catch(const std::exception& e){
    std::cerr<<"lac: "<<e.what()<<"\n";return 1;
  }
}
