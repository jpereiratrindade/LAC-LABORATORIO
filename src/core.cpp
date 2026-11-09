#include "lac/core.hpp"
#include <openssl/evp.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <fcntl.h>
#include <cerrno>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

namespace lac {
namespace {
struct Stmt {
  sqlite3_stmt* p{};
  Stmt(sqlite3* db, const std::string& sql) {
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &p, nullptr) != SQLITE_OK)
      throw std::runtime_error(sqlite3_errmsg(db));
  }
  ~Stmt() { sqlite3_finalize(p); }
  Stmt(const Stmt&)=delete;
  Stmt& operator=(const Stmt&)=delete;
  void bind(int index, const std::string& value) {
    if (sqlite3_bind_text(p, index, value.c_str(), static_cast<int>(value.size()), SQLITE_TRANSIENT) != SQLITE_OK)
      throw std::runtime_error("sqlite bind text failed");
  }
  void bind(int index, int64_t value) {
    if (sqlite3_bind_int64(p, index, value) != SQLITE_OK)
      throw std::runtime_error("sqlite bind integer failed");
  }
  void bind_null(int index) {
    if (sqlite3_bind_null(p, index) != SQLITE_OK)
      throw std::runtime_error("sqlite bind null failed");
  }
  int step() {
    int rc = sqlite3_step(p);
    if (rc != SQLITE_ROW && rc != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(sqlite3_db_handle(p)));
    return rc;
  }
  int64_t number(int index) const { return sqlite3_column_int64(p,index); }
  std::string str(int index) const {
    const auto* ptxt = sqlite3_column_text(p,index);
    return ptxt ? reinterpret_cast<const char*>(ptxt) : "";
  }
};

struct Transaction {
  Sqlite& db; bool committed=false;
  explicit Transaction(Sqlite& d):db(d){ db.exec("BEGIN IMMEDIATE"); }
  void commit() { db.exec("COMMIT"); committed=true; }
  ~Transaction() { if (!committed) { try { db.exec("ROLLBACK"); } catch(...){} } }
};

int project_id(Sqlite& db, const std::string& name, bool create=true) {
  if (name.empty() || name.size()>120) throw std::runtime_error("project name must contain 1-120 characters");
  if (create) {
    Stmt add(db.db,"INSERT OR IGNORE INTO projects(name,created_at) VALUES (?,?)");
    add.bind(1,name); add.bind(2,utc_now()); add.step();
  }
  Stmt get(db.db,"SELECT id FROM projects WHERE name=?");
  get.bind(1,name);
  return get.step()==SQLITE_ROW ? static_cast<int>(get.number(0)) : 0;
}
std::string canonical_data(const Event& e) {
  const std::array<std::string,12> parts={std::to_string(e.id),std::to_string(e.project_id),e.kind,
    e.title,e.body,e.source_type,e.source_ref,e.occurred_at,e.recorded_at,
    e.evidence_state,e.dedupe_key,e.prev_hash};
  std::string out="LAC-EVENT-v1:";
  for (const auto& v: parts) { out+=std::to_string(v.size())+":"+v; }
  return out;
}
Event event_row(Stmt& s) {
  Event e;
  e.id=s.number(0); e.project_id=static_cast<int>(s.number(1)); e.project=s.str(2);
  e.kind=s.str(3);e.title=s.str(4);e.body=s.str(5);e.source_type=s.str(6);e.source_ref=s.str(7);
  e.occurred_at=s.str(8);e.recorded_at=s.str(9);e.evidence_state=s.str(10);
  e.dedupe_key=s.str(11);e.prev_hash=s.str(12);e.event_hash=s.str(13);
  return e;
}
const char* select_events = "SELECT e.id,e.project_id,COALESCE(p.name,''),e.kind,e.title,e.body,e.source_type,"
"e.source_ref,e.occurred_at,e.recorded_at,e.evidence_state,e.dedupe_key,e.prev_hash,e.event_hash "
"FROM events e LEFT JOIN projects p ON p.id=e.project_id ";

std::string sha_file(const fs::path& p) {
  std::ifstream file(p,std::ios::binary);
  if (!file) throw std::runtime_error("cannot open: "+p.string());
  EVP_MD_CTX* ctx=EVP_MD_CTX_new();
  if (!ctx) throw std::runtime_error("openssl ctx allocation failed");
  std::array<char,32768> buf{}; unsigned char out[EVP_MAX_MD_SIZE]; unsigned int len=0;
  if (EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)!=1){ EVP_MD_CTX_free(ctx); throw std::runtime_error("openssl init failed"); }
  while (file) {
    file.read(buf.data(),static_cast<std::streamsize>(buf.size()));
    const auto n=file.gcount();
    if (n>0 && EVP_DigestUpdate(ctx,buf.data(),static_cast<size_t>(n))!=1) {
      EVP_MD_CTX_free(ctx); throw std::runtime_error("openssl digest failed");
    }
  }
  if (file.bad() || EVP_DigestFinal_ex(ctx,out,&len)!=1) { EVP_MD_CTX_free(ctx);throw std::runtime_error("file digest failed"); }
  EVP_MD_CTX_free(ctx);
  std::ostringstream os;
  for (unsigned i=0;i<len;++i) os<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<int>(out[i]);
  return os.str();
}

std::string exec_git(const fs::path& path) {
  int fds[2]; if(pipe(fds)!=0) throw std::runtime_error("pipe failed");
  pid_t pid=fork();
  if(pid<0){close(fds[0]);close(fds[1]);throw std::runtime_error("fork failed");}
  if(pid==0){
    dup2(fds[1],STDOUT_FILENO);
    // Ignore git diagnostics in captured evidence; nonzero exit is reported by parent.
    close(fds[0]);close(fds[1]);
    const std::string p=path.string();
    const char* args[]={"git","-C",p.c_str(),"log","--all","--max-count=1000",
      "--format=%H%x1f%cI%x1f%s%x1e",nullptr};
    execvp("git",const_cast<char* const*>(args)); _exit(127);
  }
  close(fds[1]);
  std::string data; std::array<char,8192> buf{};
  bool too_big=false;
  while(true){
    ssize_t n=read(fds[0],buf.data(),buf.size());
    if(n<0){if(errno==EINTR) continue;break;}
    if(n==0) break;
    if(data.size()+static_cast<size_t>(n)>(8U<<20)) { too_big=true;break; }
    data.append(buf.data(),static_cast<size_t>(n));
  }
  close(fds[0]);
  if(too_big) kill(pid,SIGKILL);
  int status=0;
  if(waitpid(pid,&status,0)<0 || too_big || !WIFEXITED(status) || WEXITSTATUS(status)!=0)
    throw std::runtime_error("git log failed for "+path.string()+" (limit 1000 commits/8MiB)");
  return data;
}

bool supported_doc(const fs::path& p) {
  static const std::set<std::string> exts={".pdf",".md",".txt",".tex"};
  std::string ext=p.extension().string();
  std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
  return exts.contains(ext);
}
bool ignored_dir(const fs::path& p) {
  static const std::set<std::string> names={".git","build","output","node_modules",".venv",
    "__pycache__",".cache",".idea",".tox",".pytest_cache","target","dist"};
  return names.contains(p.filename().string());
}
std::string make_fts_query(const std::string& str) {
  std::istringstream is(str); std::string token, result;
  int count=0;
  while(is>>token && count<12){
    std::string clean;
    for(unsigned char ch:token) if((ch>='a'&&ch<='z')||(ch>='A'&&ch<='Z')||
      (ch>='0'&&ch<='9')||ch>=128) clean+=static_cast<char>(ch);
    if(clean.empty())continue;
    if(!result.empty()) result+=" AND ";
    result+='"'+clean+'"';++count;
  }
  return result;
}
std::string get_query(const std::map<std::string,std::string>& q,const std::string& key){
  auto it=q.find(key);return it==q.end()?"":it->second;
}
int query_limit(const std::string& s) {try{return std::clamp(std::stoi(s),1,200);}catch(...){return 100;}}
} // namespace

Sqlite::Sqlite(const fs::path& path) {
  if(path.has_parent_path()) fs::create_directories(path.parent_path());
  if(sqlite3_open_v2(path.string().c_str(),&db,SQLITE_OPEN_READWRITE|SQLITE_OPEN_CREATE|SQLITE_OPEN_FULLMUTEX,nullptr)!=SQLITE_OK){
    const std::string e=db?sqlite3_errmsg(db):"open failed";if(db)sqlite3_close(db);db=nullptr;throw std::runtime_error(e);
  }
  sqlite3_busy_timeout(db,5000);
  exec("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;");
}
Sqlite::~Sqlite(){if(db)sqlite3_close(db);}
void Sqlite::exec(const std::string& sql) {
  char* error=nullptr;
  if(sqlite3_exec(db,sql.c_str(),nullptr,nullptr,&error)!=SQLITE_OK){
    const std::string msg=error?error:"sqlite error";sqlite3_free(error);throw std::runtime_error(msg);
  }
}
std::string utc_now() {
  const auto now=std::chrono::system_clock::now();
  const auto epoch=std::chrono::system_clock::to_time_t(now);
  std::tm tm{};gmtime_r(&epoch,&tm);
  std::ostringstream os;os<<std::put_time(&tm,"%Y-%m-%dT%H:%M:%SZ");return os.str();
}
std::string sha256(const std::string& value) {
  unsigned char out[EVP_MAX_MD_SIZE];unsigned int len=0;
  EVP_Digest(value.data(),value.size(),out,&len,EVP_sha256(),nullptr);
  std::ostringstream os;
  for(unsigned i=0;i<len;++i)os<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<int>(out[i]);
  return os.str();
}
void initialize(Sqlite& db) {
  // Check the version before any schema write to avoid modifying future databases.
  {
    Stmt ver(db.db,"PRAGMA user_version");ver.step();
    if(ver.number(0)>1)throw std::runtime_error("database schema is newer than this lac binary");
  }
  db.exec(R"SQL(
    CREATE TABLE IF NOT EXISTS projects(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS roots(
      id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
      kind TEXT NOT NULL CHECK(kind IN ('git','docs')),
      path TEXT NOT NULL, scan_counter INTEGER NOT NULL DEFAULT 0,
      UNIQUE(kind,path));
    CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER REFERENCES projects(id),
      kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
      source_type TEXT NOT NULL CHECK(source_type IN ('git','file','manual')),
      source_ref TEXT NOT NULL, occurred_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
      evidence_state TEXT NOT NULL CHECK(evidence_state IN ('observed','declared','proposed')),
      dedupe_key TEXT NOT NULL UNIQUE, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
      BEGIN SELECT RAISE(ABORT,'append-only events'); END;
    CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
      BEGIN SELECT RAISE(ABORT,'append-only events'); END;
    CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(title,body,source_ref,
      tokenize='unicode61 remove_diacritics 2');
    CREATE TRIGGER IF NOT EXISTS event_fts_ai AFTER INSERT ON events BEGIN
      INSERT INTO event_fts(rowid,title,body,source_ref)
      VALUES(new.id,new.title,new.body,new.source_ref);
    END;
    CREATE TABLE IF NOT EXISTS file_snapshots(
      root_id INTEGER NOT NULL REFERENCES roots(id), path TEXT NOT NULL,
      hash TEXT NOT NULL, bytes INTEGER NOT NULL,
      revision INTEGER NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
      seen_scan INTEGER NOT NULL, PRIMARY KEY(root_id,path));
    CREATE TABLE IF NOT EXISTS relations(
      id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL UNIQUE REFERENCES events(id),
      from_project INTEGER NOT NULL REFERENCES projects(id),
      to_project INTEGER NOT NULL REFERENCES projects(id),
      label TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('candidate','user_confirmed')));
    CREATE TABLE IF NOT EXISTS continuity_jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id INTEGER NOT NULL REFERENCES events(id),
      root_id INTEGER NOT NULL REFERENCES roots(id),
      path TEXT NOT NULL, kind TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('pending','processing','completed','failed')),
      attempts INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      error_message TEXT);
    CREATE INDEX IF NOT EXISTS jobs_state ON continuity_jobs(state, id ASC);
    CREATE TABLE IF NOT EXISTS continuity_insights(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      job_id INTEGER REFERENCES continuity_jobs(id),
      event_id INTEGER NOT NULL REFERENCES events(id),
      project_id INTEGER NOT NULL REFERENCES projects(id),
      document_path TEXT NOT NULL, summary TEXT NOT NULL,
      gaps_json TEXT NOT NULL, model TEXT NOT NULL,
      created_at TEXT NOT NULL, event_hash TEXT NOT NULL,
      relations_json TEXT DEFAULT '[]');
    CREATE INDEX IF NOT EXISTS insights_project ON continuity_insights(project_id, created_at DESC);
    CREATE TABLE IF NOT EXISTS continuity_feedback(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      insight_id INTEGER REFERENCES continuity_insights(id),
      project_id INTEGER NOT NULL REFERENCES projects(id),
      target_type TEXT NOT NULL CHECK(target_type IN ('insight', 'gap', 'relation')),
      target_ref TEXT NOT NULL,
      decision TEXT NOT NULL CHECK(decision IN ('adopted', 'dismissed', 'corrected')),
      reason TEXT,
      actor TEXT NOT NULL,
      created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS feedback_project ON continuity_feedback(project_id, target_type, target_ref);
    CREATE INDEX IF NOT EXISTS events_occurred ON events(occurred_at DESC,id DESC);
    CREATE INDEX IF NOT EXISTS events_project ON events(project_id,occurred_at DESC);
  )SQL");
  try { db.exec("ALTER TABLE continuity_insights ADD COLUMN relations_json TEXT DEFAULT '[]'"); } catch(...) {}
  db.exec("PRAGMA user_version=1");
  Stmt fts(db.db,"SELECT sqlite_compileoption_used('ENABLE_FTS5')");
  if(fts.step()!=SQLITE_ROW || fts.number(0)==0)throw std::runtime_error("SQLite FTS5 required");
}

int register_root(Sqlite& db,const std::string& project,const fs::path& path,const std::string& kind) {
  if(kind!="git"&&kind!="docs")throw std::runtime_error("kind must be git or docs");
  if(!fs::is_directory(path)) throw std::runtime_error("root path must be an existing directory");
  const std::string canonical=fs::canonical(path).string();
  Transaction tx(db);
  int p=project_id(db,project);
  Stmt existing(db.db,"SELECT project_id FROM roots WHERE kind=? AND path=?");
  existing.bind(1,kind);existing.bind(2,canonical);
  if(existing.step()==SQLITE_ROW && existing.number(0)!=p)
    throw std::runtime_error("path already belongs to a different project");
  Stmt add(db.db,"INSERT OR IGNORE INTO roots(project_id,kind,path) VALUES(?,?,?)");
  add.bind(1,p);add.bind(2,kind);add.bind(3,canonical);add.step();
  Stmt get(db.db,"SELECT id FROM roots WHERE kind=? AND path=?");
  get.bind(1,kind);get.bind(2,canonical);get.step();int id=static_cast<int>(get.number(0));
  tx.commit();return id;
}
std::vector<Root> roots(Sqlite& db) {
  Stmt s(db.db,"SELECT r.id,r.project_id,p.name,r.kind,r.path FROM roots r JOIN projects p ON p.id=r.project_id ORDER BY p.name,r.kind");
  std::vector<Root> out;
  while(s.step()==SQLITE_ROW)out.push_back({static_cast<int>(s.number(0)),static_cast<int>(s.number(1)),s.str(2),s.str(3),s.str(4)});
  return out;
}
int64_t append_event(Sqlite& db,Event event) {
  Stmt existing(db.db,"SELECT id FROM events WHERE dedupe_key=?");existing.bind(1,event.dedupe_key);
  if(existing.step()==SQLITE_ROW)return 0;
  Stmt last(db.db,"SELECT id,event_hash FROM events ORDER BY id DESC LIMIT 1");
  int64_t previous=0;
  if(last.step()==SQLITE_ROW){previous=last.number(0);event.prev_hash=last.str(1);}
  else event.prev_hash="GENESIS";
  event.id=previous+1;
  if(event.recorded_at.empty())event.recorded_at=utc_now();
  event.event_hash=sha256(canonical_data(event));
  Stmt add(db.db,R"SQL(INSERT INTO events(id,project_id,kind,title,body,source_type,
       source_ref,occurred_at,recorded_at,evidence_state,dedupe_key,prev_hash,event_hash)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?))SQL");
  add.bind(1,event.id);add.bind(2,event.project_id);add.bind(3,event.kind);add.bind(4,event.title);
  add.bind(5,event.body);add.bind(6,event.source_type);add.bind(7,event.source_ref);
  add.bind(8,event.occurred_at);add.bind(9,event.recorded_at);add.bind(10,event.evidence_state);
  add.bind(11,event.dedupe_key);add.bind(12,event.prev_hash);add.bind(13,event.event_hash);
  add.step();return event.id;
}
int scan_root(Sqlite& db,const Root& root) {
  if(!fs::is_directory(root.path))throw std::runtime_error("root unavailable: "+root.path);
  Transaction tx(db);
  int appended=0;
  if(root.kind=="git") {
    const auto data=exec_git(root.path);
    size_t pos=0;
    while(pos<data.size()){
      const size_t end=data.find('\x1e',pos);
      if(end==std::string::npos)break;
      std::string record=data.substr(pos,end-pos);
      pos=end+1;
      while(!record.empty() && (record[0]=='\n'||record[0]=='\r'))record.erase(0,1);
      const size_t a=record.find('\x1f');
      const size_t b=a==std::string::npos?std::string::npos:record.find('\x1f',a+1);
      if(a==std::string::npos||b==std::string::npos)continue;
      const auto hash=record.substr(0,a),when=record.substr(a+1,b-a-1),subject=record.substr(b+1);
      if(hash.size()!=40 && hash.size()!=64)continue;
      Event e;e.project_id=root.project_id;e.kind="git_commit";e.title=subject;
      e.body="Commit " + hash.substr(0,12)+" (mensagem do autor; não prova decisão implementada)";
      e.source_type="git";e.source_ref=root.path+"#"+hash;
      e.occurred_at=when;e.evidence_state="observed";
      e.dedupe_key="git:"+std::to_string(root.id)+":"+hash;
      if(append_event(db,e)>0)++appended;
    }
  } else {
    Stmt run(db.db,"UPDATE roots SET scan_counter=scan_counter+1 WHERE id=?");run.bind(1,root.id);run.step();
    Stmt counter(db.db,"SELECT scan_counter FROM roots WHERE id=?");counter.bind(1,root.id);counter.step();
    const auto scan=counter.number(0);
    size_t count=0;
    std::error_code ec;
    for(fs::recursive_directory_iterator it(root.path,fs::directory_options::none,ec),end;
        it!=end;it.increment(ec)){
      if(ec)throw std::runtime_error("filesystem enumeration failed: "+ec.message());
      const auto& entry=*it;
      if(entry.is_symlink(ec)){if(entry.is_directory(ec))it.disable_recursion_pending();continue;}
      if(entry.is_directory(ec)){if(ignored_dir(entry.path()))it.disable_recursion_pending();continue;}
      if(!entry.is_regular_file(ec)||!supported_doc(entry.path()))continue;
      if(++count>5000)throw std::runtime_error("5000 supported documents limit exceeded; split the registered root");
      const auto bytes=entry.file_size(ec);
      if(ec)throw std::runtime_error("failed to stat file: "+entry.path().string());
      if(bytes>32U*1024U*1024U)continue; // never claim indexed evidence for skipped large files
      const std::string relative=fs::relative(entry.path(),root.path).generic_string();
      const std::string hash=sha_file(entry.path());
      Stmt previous(db.db,"SELECT hash,revision,active FROM file_snapshots WHERE root_id=? AND path=?");
      previous.bind(1,root.id);previous.bind(2,relative);
      const bool exists=previous.step()==SQLITE_ROW;
      const std::string old_hash=exists?previous.str(0):"";
      const int64_t revision=exists?previous.number(1)+1:1;
      const bool old_active=exists&&previous.number(2)!=0;
      if(!exists || old_hash!=hash || !old_active){
        Event e;e.project_id=root.project_id;e.kind=!old_active?"file_added":"file_changed";
        e.title=relative;
        e.body="SHA-256: "+hash+" | bytes: "+std::to_string(bytes)+
               (old_active?" | SHA-256 anterior: "+old_hash:"");
        e.source_type="file";e.source_ref=entry.path().string();
        e.occurred_at=utc_now();e.evidence_state="observed";
        e.dedupe_key="file:"+std::to_string(root.id)+":"+relative+":"+std::to_string(revision);
        const auto new_id=append_event(db,e);
        if(new_id>0){
          ++appended;
          Stmt job(db.db,R"SQL(INSERT INTO continuity_jobs(event_id,root_id,path,kind,state,created_at,updated_at)
                   VALUES(?,?,?,?,'pending',?,?))SQL");
          job.bind(1,new_id);job.bind(2,root.id);job.bind(3,relative);job.bind(4,e.kind);
          job.bind(5,e.occurred_at);job.bind(6,e.occurred_at);job.step();
        }
      }
      Stmt up(db.db,R"SQL(INSERT INTO file_snapshots(root_id,path,hash,bytes,revision,active,seen_scan)
        VALUES(?,?,?,?,?,1,?) ON CONFLICT(root_id,path) DO UPDATE SET
        hash=excluded.hash,bytes=excluded.bytes,revision=excluded.revision,
        active=1,seen_scan=excluded.seen_scan)SQL");
      up.bind(1,root.id);up.bind(2,relative);up.bind(3,hash);up.bind(4,static_cast<int64_t>(bytes));
      up.bind(5,exists && old_hash==hash && old_active?revision-1:revision);up.bind(6,scan);up.step();
    }
    Stmt missing(db.db,"SELECT path,revision,hash FROM file_snapshots WHERE root_id=? AND active=1 AND seen_scan!=?");
    missing.bind(1,root.id);missing.bind(2,scan);
    struct Missing{std::string path;int64_t revision;std::string hash;};
    std::vector<Missing> disappeared;
    while(missing.step()==SQLITE_ROW)disappeared.push_back({missing.str(0),missing.number(1),missing.str(2)});
    for(const auto& m:disappeared){
      Event e;e.project_id=root.project_id;e.kind="file_missing";e.title=m.path;
      e.body="Arquivo não encontrado na varredura; último SHA-256: "+m.hash+
            ". Pode ter sido movido, excluído ou ultrapassado o limite de 32 MiB.";
      e.source_type="file";e.source_ref=(fs::path(root.path)/m.path).string();
      e.occurred_at=utc_now();e.evidence_state="observed";
      e.dedupe_key="file:"+std::to_string(root.id)+":"+m.path+":"+std::to_string(m.revision+1);
      if(append_event(db,e)>0)++appended;
      Stmt up(db.db,"UPDATE file_snapshots SET active=0,revision=revision+1 WHERE root_id=? AND path=?");
      up.bind(1,root.id);up.bind(2,m.path);up.step();
    }
  }
  tx.commit();return appended;
}
int scan_all(Sqlite& db) {int changed=0;for(const auto& root:roots(db))changed+=scan_root(db,root);return changed;}
bool verify_chain(Sqlite& db,std::string& error) {
  Stmt s(db.db,std::string(select_events)+"ORDER BY e.id ASC");
  std::string prev="GENESIS";int64_t id=0;
  while(s.step()==SQLITE_ROW){
    const Event e=event_row(s);
    if(e.id!=id+1||e.prev_hash!=prev||sha256(canonical_data(e))!=e.event_hash){
      error="integrity divergence at event id="+std::to_string(e.id);return false;
    }
    prev=e.event_hash;id=e.id;
  }
  error="OK "+std::to_string(id)+" eventos; cadeia SHA-256 consistente";
  return true;
}
int64_t record_note(Sqlite& db,const std::string& project,const std::string& kind,
  const std::string& title,const std::string& body,const std::string& reference,bool llm){
  if(kind!="note"&&kind!="decision"&&kind!="todo"&&kind!="correction")
    throw std::runtime_error("kind must be note, decision, todo or correction");
  if(title.empty()||title.size()>200||body.size()>8000||reference.size()>3000)
    throw std::runtime_error("invalid title/body/reference lengths");
  Transaction tx(db);
  Event e;e.project_id=project_id(db,project);e.kind=kind;e.title=title;e.body=body;
  e.source_type="manual";e.source_ref=reference.empty()?"manual-entry":reference;
  if(llm)e.source_ref="llm:mcp:"+e.source_ref;
  e.occurred_at=utc_now();e.evidence_state="declared";
  // Unique explicit capture ID; no deduplication of distinct human declarations.
  e.dedupe_key="manual:"+sha256(utc_now()+title+body+std::to_string(sqlite3_total_changes(db.db))+
                        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  auto id=append_event(db,e);tx.commit();return id;
}
int64_t close_todo(Sqlite& db,int64_t todo_id,bool llm) {
  Transaction tx(db);
  Stmt get(db.db,"SELECT project_id,title FROM events WHERE id=? AND kind='todo'");
  get.bind(1,todo_id);
  if(get.step()!=SQLITE_ROW)throw std::runtime_error("todo does not exist");
  const auto project=static_cast<int>(get.number(0));const auto title=get.str(1);
  Stmt done(db.db,"SELECT 1 FROM events WHERE kind='todo_closed' AND (source_ref=? OR source_ref='llm:mcp:' || ?)");
  done.bind(1,"todo:"+std::to_string(todo_id));
  done.bind(2,"todo:"+std::to_string(todo_id));
  if(done.step()==SQLITE_ROW)throw std::runtime_error("todo already closed");
  Event e;e.project_id=project;e.kind="todo_closed";e.title="Concluído: "+title;
  e.body="Encerramento declarado pelo usuário; não valida automaticamente a execução.";
  e.source_type="manual";e.source_ref="todo:"+std::to_string(todo_id);
  if(llm){e.source_ref="llm:mcp:"+e.source_ref;e.body="Encerramento declarado por LLM via MCP; não valida automaticamente a execução.";}
  e.occurred_at=utc_now();e.evidence_state="declared";e.dedupe_key="todo_closed:"+std::to_string(todo_id);
  const auto id=append_event(db,e);tx.commit();return id;
}
int64_t record_relation(Sqlite& db,const std::string& from,const std::string& to,
  const std::string& label,const std::string& state,bool llm){
  if(llm&&state!="candidate")throw std::runtime_error("LLM relations must remain candidate");
  if(from==to||label.empty()||label.size()>300||
     (state!="candidate"&&state!="user_confirmed"))
    throw std::runtime_error("invalid relation; state must be candidate or user_confirmed");
  Transaction tx(db);
  const int a=project_id(db,from);const int b=project_id(db,to);
  Event e;e.project_id=a;e.kind="relation";e.title=from+" ↔ "+to;
  e.body=label+" ["+state+"]";e.source_type="manual";
  e.source_ref="relation:"+from+":"+to;e.occurred_at=utc_now();
  if(llm)e.source_ref="llm:mcp:"+e.source_ref;
  e.evidence_state=state=="candidate"?"proposed":"declared";
  e.dedupe_key="relation:"+sha256(utc_now()+from+to+label+state+
                       std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  const auto id=append_event(db,e);
  Stmt ins(db.db,"INSERT INTO relations(event_id,from_project,to_project,label,state) VALUES(?,?,?,?,?)");
  ins.bind(1,id);ins.bind(2,a);ins.bind(3,b);ins.bind(4,label);ins.bind(5,state);ins.step();
  tx.commit();return id;
}
std::string json_escape(const std::string& s){
  std::ostringstream os;
  for(unsigned char c:s){
    switch(c){case '"':os<<"\\\"";break;case '\\':os<<"\\\\";break;
      case '\b':os<<"\\b";break;case '\f':os<<"\\f";break;
      case '\n':os<<"\\n";break;case '\r':os<<"\\r";break;case '\t':os<<"\\t";break;
      default:if(c<0x20){os<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<static_cast<int>(c)<<std::dec;}
              else os<<static_cast<char>(c);
    }
  }
  return os.str();
}
std::string json_string(const std::string& s){return '"'+json_escape(s)+'"';}
std::string json_event(const Event& e) {
  return "{\"id\":"+std::to_string(e.id)+",\"project\":"+json_string(e.project)+
    ",\"kind\":"+json_string(e.kind)+",\"title\":"+json_string(e.title)+
    ",\"body\":"+json_string(e.body)+",\"actor\":"+json_string(e.source_ref.starts_with("llm:mcp:")?"llm":e.source_type=="manual"?"user":"observer")+",\"source_type\":"+json_string(e.source_type)+
    ",\"source_ref\":"+json_string(e.source_ref)+",\"occurred_at\":"+json_string(e.occurred_at)+
    ",\"recorded_at\":"+json_string(e.recorded_at)+",\"evidence_state\":"+
    json_string(e.evidence_state)+",\"event_hash\":"+json_string(e.event_hash)+"}";
}
std::string json_events(Sqlite& db,const std::map<std::string,std::string>& q){
  std::string query=std::string(select_events);
  const std::string term=get_query(q,"q"),project=get_query(q,"project"),kind=get_query(q,"kind");
  const std::string from=get_query(q,"from"),to=get_query(q,"to");
  const std::string search=make_fts_query(term);
  if(!search.empty())query+="JOIN event_fts ON event_fts.rowid=e.id ";
  query+="WHERE 1=1 ";
  if(!search.empty())query+="AND event_fts MATCH ? ";
  if(!project.empty())query+="AND p.name=? ";
  if(kind=="substantive")query+="AND e.kind NOT IN ('file_added','file_changed','file_missing') ";
  else if(!kind.empty())query+="AND e.kind=? ";
  if(!from.empty())query+="AND substr(e.occurred_at,1,10)>=? ";
  if(!to.empty())query+="AND substr(e.occurred_at,1,10)<=? ";
  query+="ORDER BY e.occurred_at DESC,e.id DESC LIMIT ?";
  Stmt s(db.db,query);int index=1;
  if(!search.empty())s.bind(index++,search);
  if(!project.empty())s.bind(index++,project);
  if(!kind.empty()&&kind!="substantive")s.bind(index++,kind);
  if(!from.empty())s.bind(index++,from);
  if(!to.empty())s.bind(index++,to);
  s.bind(index,query_limit(get_query(q,"limit")));
  std::string out="[";bool first=true;
  while(s.step()==SQLITE_ROW){if(!first)out+=",";first=false;out+=json_event(event_row(s));}
  return out+"]";
}
std::string json_documents(Sqlite& db, const std::map<std::string,std::string>& q){
  const std::string project=get_query(q,"project");
  const std::string term=get_query(q,"q");
  const std::string ext_filter=get_query(q,"ext");
  int limit=150;
  try{
    const std::string l=get_query(q,"limit");
    if(!l.empty())limit=std::min(500,std::max(10,std::stoi(l)));
  }catch(...){}

  std::string sql="SELECT e.id, e.source_ref, p.name, e.title, e.occurred_at, i.summary, i.gaps_json "
                  "FROM events e "
                  "JOIN projects p ON p.id=e.project_id "
                  "LEFT JOIN continuity_insights i ON i.event_id=e.id "
                  "WHERE e.kind IN ('file_added','file_changed') ";
  if(!project.empty())sql+="AND p.name=? ";
  if(!term.empty())sql+="AND (e.title LIKE ? OR e.source_ref LIKE ? OR (i.summary IS NOT NULL AND i.summary LIKE ?)) ";
  sql+="GROUP BY e.source_ref ";
  sql+="ORDER BY (i.summary IS NOT NULL) DESC, e.id DESC LIMIT ?";

  Stmt s(db.db,sql);
  int idx=1;
  if(!project.empty())s.bind(idx++,project);
  if(!term.empty()){
    const std::string pattern="%"+term+"%";
    s.bind(idx++,pattern);
    s.bind(idx++,pattern);
    s.bind(idx++,pattern);
  }
  s.bind(idx++,limit);

  std::string out="[";
  bool first=true;
  while(s.step()==SQLITE_ROW){
    const std::string path=s.str(1);
    std::string ext;
    const auto dot=path.rfind('.');
    if(dot!=std::string::npos)ext=path.substr(dot);
    if(!ext_filter.empty()&&ext!=ext_filter)continue;

    if(!first)out+=",";
    first=false;
    out+="{\"id\":"+std::to_string(s.number(0))+
         ",\"path\":"+json_string(path)+
         ",\"project\":"+json_string(s.str(2))+
         ",\"filename\":"+json_string(s.str(3))+
         ",\"ext\":"+json_string(ext)+
         ",\"occurred_at\":"+json_string(s.str(4))+
         ",\"has_insight\":"+std::string(s.str(5).empty()?"false":"true")+
         ",\"summary\":"+json_string(s.str(5))+
         ",\"gaps\":"+(s.str(6).empty()?"[]":s.str(6))+"}";
  }
  out+="]";
  return out;
}
std::string json_roots(Sqlite& db){
  std::string out="[";bool first=true;
  for(const auto& r:roots(db)){
    if(!first)out+=",";
    first=false;
    out+="{\"id\":"+std::to_string(r.id)+",\"project\":"+json_string(r.project)+
      ",\"kind\":"+json_string(r.kind)+",\"path\":"+json_string(r.path)+"}";
  }
  return out+"]";
}
std::string json_projects(Sqlite& db){
  Stmt s(db.db,"SELECT p.name,COUNT(e.id) FROM projects p LEFT JOIN events e ON e.project_id=p.id GROUP BY p.id ORDER BY p.name");
  std::string out="[";bool first=true;
  while(s.step()==SQLITE_ROW){if(!first)out+=",";first=false;
    out+="{\"name\":"+json_string(s.str(0)) + ",\"events\":"+std::to_string(s.number(1))+"}";}
  return out+"]";
}
std::string json_relations(Sqlite& db){
  Stmt s(db.db,"SELECT r.id,a.name,b.name,r.label,r.state,r.event_id,e.source_ref FROM relations r "
    "JOIN projects a ON a.id=r.from_project JOIN projects b ON b.id=r.to_project "
    "JOIN events e ON e.id=r.event_id ORDER BY r.id DESC LIMIT 200");
  std::string out="[";bool first=true;
  while(s.step()==SQLITE_ROW){if(!first)out+=",";first=false;
    out+="{\"id\":"+std::to_string(s.number(0))+",\"from\":"+json_string(s.str(1))+
      ",\"to\":"+json_string(s.str(2)) + ",\"label\":"+json_string(s.str(3))+
      ",\"state\":"+json_string(s.str(4)) + ",\"actor\":"+json_string(s.str(6).starts_with("llm:mcp:")?"llm":"user")+
      ",\"event_id\":"+std::to_string(s.number(5))+"}";}
  return out+"]";
}
std::string json_todos(Sqlite& db){
  Stmt s(db.db,"SELECT e.id,p.name,e.title,e.body,e.occurred_at,e.source_ref FROM events e JOIN projects p ON p.id=e.project_id "
    "WHERE e.kind='todo' AND NOT EXISTS(SELECT 1 FROM events x WHERE x.kind='todo_closed' "
    "AND x.dedupe_key=('todo_closed:' || e.id)) ORDER BY e.occurred_at DESC LIMIT 200");
  std::string out="[";bool first=true;
  while(s.step()==SQLITE_ROW){if(!first)out+=",";first=false;
    out+="{\"id\":"+std::to_string(s.number(0))+",\"project\":"+json_string(s.str(1))+
      ",\"title\":"+json_string(s.str(2)) + ",\"body\":"+json_string(s.str(3))+
      ",\"actor\":"+json_string(s.str(5).starts_with("llm:mcp:")?"llm":"user")+
      ",\"occurred_at\":"+json_string(s.str(4))+"}";}
  return out+"]";
}
std::string json_continuity_insights(Sqlite& db, const std::string& project) {
  std::string sql = "SELECT i.id, i.event_id, p.name, e.source_ref, i.summary, i.gaps_json, i.model, i.created_at, i.event_hash, COALESCE(i.relations_json, '[]') "
                    "FROM continuity_insights i JOIN projects p ON p.id=i.project_id JOIN events e ON e.id=i.event_id "
                    "WHERE i.id NOT IN (SELECT insight_id FROM continuity_feedback WHERE target_type='insight' AND decision='dismissed' AND insight_id IS NOT NULL) ";
  if(!project.empty()) sql += "AND p.name=? ";
  sql += "ORDER BY i.id DESC LIMIT 50";
  Stmt s(db.db, sql);
  if(!project.empty()) s.bind(1, project);
  std::string out = "[";
  bool first = true;
  while(s.step() == SQLITE_ROW) {
    if(!first) out += ",";
    first = false;
    out += "{\"id\":" + std::to_string(s.number(0)) +
           ",\"event_id\":" + std::to_string(s.number(1)) +
           ",\"project\":" + json_string(s.str(2)) +
           ",\"document_path\":" + json_string(s.str(3)) +
           ",\"summary\":" + json_string(s.str(4)) +
           ",\"gaps\":" + (s.str(5).empty() ? "[]" : s.str(5)) +
           ",\"model\":" + json_string(s.str(6)) +
           ",\"created_at\":" + json_string(s.str(7)) +
           ",\"event_hash\":" + json_string(s.str(8)) +
           ",\"relations\":" + (s.str(9).empty() ? "[]" : s.str(9)) + "}";
  }
  out += "]";
  return out;
}
std::string json_continuity_jobs(Sqlite& db) {
  Stmt s(db.db, "SELECT state, count(*) FROM continuity_jobs GROUP BY state");
  std::map<std::string, int64_t> counts;
  while(s.step() == SQLITE_ROW) {
    counts[s.str(0)] = s.number(1);
  }
  return "{\"pending\":" + std::to_string(counts["pending"]) +
         ",\"processing\":" + std::to_string(counts["processing"]) +
         ",\"completed\":" + std::to_string(counts["completed"]) +
         ",\"failed\":" + std::to_string(counts["failed"]) + "}";
}
int64_t record_feedback(Sqlite& db, int64_t insight_id, const std::string& project,
                        const std::string& target_type, const std::string& target_ref,
                        const std::string& decision, const std::string& reason,
                        const std::string& actor){
  if(target_type != "insight" && target_type != "gap" && target_type != "relation")
    throw std::runtime_error("target_type must be insight, gap, or relation");
  if(decision != "adopted" && decision != "dismissed" && decision != "corrected")
    throw std::runtime_error("decision must be adopted, dismissed, or corrected");
  if(target_ref.empty() || target_ref.size() > 500)
    throw std::runtime_error("target_ref required (max 500 chars)");
  if(reason.size() > 2000)
    throw std::runtime_error("reason exceeds 2000 chars");
  Transaction tx(db);
  const int p = project_id(db, project);
  Stmt ins(db.db, "INSERT INTO continuity_feedback(insight_id, project_id, target_type, target_ref, decision, reason, actor, created_at) VALUES(?,?,?,?,?,?,?,?)");
  if(insight_id > 0) ins.bind(1, insight_id);
  else ins.bind_null(1);
  ins.bind(2, static_cast<int64_t>(p));
  ins.bind(3, target_type);
  ins.bind(4, target_ref);
  ins.bind(5, decision);
  ins.bind(6, reason);
  ins.bind(7, actor.empty() ? "user" : actor);
  ins.bind(8, utc_now());
  ins.step();
  const auto id = sqlite3_last_insert_rowid(db.db);
  tx.commit();
  return id;
}
std::string json_continuity_feedback(Sqlite& db, const std::string& project){
  std::string sql = "SELECT f.id, COALESCE(f.insight_id, 0), p.name, f.target_type, f.target_ref, f.decision, COALESCE(f.reason, ''), f.actor, f.created_at "
                    "FROM continuity_feedback f JOIN projects p ON p.id=f.project_id ";
  if(!project.empty()) sql += "WHERE p.name=? ";
  sql += "ORDER BY f.id DESC LIMIT 50";
  Stmt s(db.db, sql);
  if(!project.empty()) s.bind(1, project);
  std::string out = "[";
  bool first = true;
  while(s.step() == SQLITE_ROW){
    if(!first) out += ",";
    first = false;
    out += "{\"id\":" + std::to_string(s.number(0)) +
           ",\"insight_id\":" + std::to_string(s.number(1)) +
           ",\"project\":" + json_string(s.str(2)) +
           ",\"target_type\":" + json_string(s.str(3)) +
           ",\"target_ref\":" + json_string(s.str(4)) +
           ",\"decision\":" + json_string(s.str(5)) +
           ",\"reason\":" + json_string(s.str(6)) +
           ",\"actor\":" + json_string(s.str(7)) +
           ",\"created_at\":" + json_string(s.str(8)) + "}";
  }
  out += "]";
  return out;
}
std::string json_stats(Sqlite& db){
  Stmt s(db.db,"SELECT (SELECT COUNT(*) FROM projects),(SELECT COUNT(*) FROM roots),"
    "(SELECT COUNT(*) FROM events),(SELECT COUNT(*) FROM relations),"
    "(SELECT COUNT(*) FROM events WHERE kind='todo' AND NOT EXISTS(SELECT 1 FROM events x "
    "WHERE x.kind='todo_closed' AND x.dedupe_key=('todo_closed:' || events.id)))");
  s.step();
  return "{\"projects\":"+std::to_string(s.number(0)) + ",\"roots\":"+std::to_string(s.number(1))+
    ",\"events\":"+std::to_string(s.number(2)) + ",\"relations\":"+std::to_string(s.number(3))+
    ",\"open_todos\":"+std::to_string(s.number(4)) + ",\"now_utc\":"+json_string(utc_now())+"}";
}
} // namespace lac

namespace lac {
namespace {
std::string md_escape(std::string s) {
  // Avoid accidental markdown heading/list injection in generated prose.
  for(char& c:s)if(c=='\r')c=' ';
  return s;
}
}
std::string markdown_report(Sqlite& db,const std::map<std::string,std::string>& q){
  const auto from=get_query(q,"from"),to=get_query(q,"to"),project=get_query(q,"project");
  std::string sql=std::string(select_events)+"WHERE 1=1 ";
  if(!from.empty())sql+="AND substr(e.occurred_at,1,10)>=? ";
  if(!to.empty())sql+="AND substr(e.occurred_at,1,10)<=? ";
  if(!project.empty())sql+="AND p.name=? ";
  sql+="ORDER BY e.occurred_at ASC,e.id ASC LIMIT 5000";
  Stmt s(db.db,sql);int i=1;
  if(!from.empty())s.bind(i++,from);
  if(!to.empty())s.bind(i++,to);
  if(!project.empty())s.bind(i++,project);
  std::string out="# LAC — Diário da continuidade\n\n";
  out+="- Intervalo de ocorrência: "+(from.empty()?"início":from)+" a "+(to.empty()?"presente":to)+"\n";
  out+="- Gerado em UTC: "+utc_now()+"\n";
  out+="- Limite de exportação: 5000 eventos\n\n";
  out+="**Critério:** observações são rastros de alterações, declarações são humanas, "
       "relações propostas não são causalidade comprovada.\n\n";
  size_t count=0;std::string date;
  while(s.step()==SQLITE_ROW){
    const auto e=event_row(s);
    const auto d=e.occurred_at.substr(0,10);
    if(d!=date){date=d;out+="\n## "+date+"\n\n";}
    out+="### #"+std::to_string(e.id)+" — "+md_escape(e.title)+"\n\n";
    out+="- Projeto: "+md_escape(e.project)+"\n";
    out+="- Natureza: "+e.kind+" / "+e.evidence_state+"\n";
    out+="- Ocorrência: "+e.occurred_at+"\n";
    out+="- Registro: "+e.recorded_at+"\n";
    out+="- Origem: `"+md_escape(e.source_ref)+"`\n";
    out+="- Hash do evento: `"+e.event_hash+"`\n\n";
    if(!e.body.empty())out+=md_escape(e.body)+"\n\n";
    ++count;
  }
  out+="\n---\n**Total exportado:** "+std::to_string(count)+" eventos.\n";
  return out;
}
void write_anchor(Sqlite& db,const fs::path& path){
  Stmt s(db.db,"SELECT id,event_hash FROM events ORDER BY id DESC LIMIT 1");
  const bool has=s.step()==SQLITE_ROW;
  const auto id=has?s.number(0):0;
  const auto hash=has?s.str(1):"GENESIS";
  if(path.has_parent_path())fs::create_directories(path.parent_path());
  // O_EXCL avoids silently rewriting an independent reference point.
  const int fd=open(path.string().c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
  if(fd<0)throw std::runtime_error("cannot create anchor (file must not exist): "+path.string());
  const std::string content="LAC-ANCHOR-v1\t"+std::to_string(id)+"\t"+hash+"\t"+utc_now()+"\n";
  const ssize_t n=write(fd,content.data(),content.size());
  if(n!=static_cast<ssize_t>(content.size())||fsync(fd)!=0){close(fd);throw std::runtime_error("anchor write failure");}
  close(fd);
}
bool verify_anchor(Sqlite& db,const fs::path& path,std::string& error){
  std::ifstream input(path);std::string line;
  if(!std::getline(input,line)){error="anchor missing or empty";return false;}
  std::istringstream fields(line);std::string version,idstr,hash,date;
  if(!std::getline(fields,version,'\t')||!std::getline(fields,idstr,'\t')||
     !std::getline(fields,hash,'\t')||!std::getline(fields,date,'\t')||
     version!="LAC-ANCHOR-v1"){
    error="invalid anchor format";return false;
  }
  int64_t id;
  try{id=std::stoll(idstr);}catch(...){error="invalid anchor id";return false;}
  if(id<0){error="negative anchor id";return false;}
  if(id==0){if(hash=="GENESIS"){error="genesis anchor validated";return true;}
    error="genesis anchor mismatch";return false;}
  Stmt s(db.db,"SELECT event_hash FROM events WHERE id=?");s.bind(1,id);
  if(s.step()!=SQLITE_ROW || s.str(0)!=hash){
    error="external anchor mismatch at event #"+std::to_string(id);return false;
  }
  error="external anchor verified at event #"+std::to_string(id);return true;
}
} // namespace lac
