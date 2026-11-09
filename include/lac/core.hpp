#pragma once
#include <sqlite3.h>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>
#include <map>

namespace lac {
namespace fs = std::filesystem;

struct Root {
  int id{};
  int project_id{};
  std::string project;
  std::string kind;
  std::string path;
};

struct Event {
  int64_t id{};
  int project_id{};
  std::string project;
  std::string kind, title, body, source_type, source_ref;
  std::string occurred_at, recorded_at, evidence_state, dedupe_key, prev_hash, event_hash;
};

struct Sqlite {
  sqlite3* db{};
  explicit Sqlite(const fs::path& path);
  ~Sqlite();
  Sqlite(const Sqlite&)=delete;
  Sqlite& operator=(const Sqlite&)=delete;
  void exec(const std::string& sql);
};

std::string utc_now();
std::string sha256(const std::string& data);
std::string json_escape(const std::string& value);
std::string json_string(const std::string& value);
std::string json_event(const Event& event);
std::string json_roots(Sqlite& db);
std::string json_projects(Sqlite& db);
std::string json_relations(Sqlite& db);
std::string json_stats(Sqlite& db);
std::string json_events(Sqlite& db, const std::map<std::string,std::string>& query);
std::string json_todos(Sqlite& db);
std::string markdown_report(Sqlite& db, const std::map<std::string,std::string>& query);
void write_anchor(Sqlite& db, const fs::path& path);
bool verify_anchor(Sqlite& db, const fs::path& path, std::string& error);

void initialize(Sqlite& db);
int register_root(Sqlite& db, const std::string& project, const fs::path& path, const std::string& kind);
std::vector<Root> roots(Sqlite& db);
int scan_all(Sqlite& db);
int scan_root(Sqlite& db, const Root& root);
bool verify_chain(Sqlite& db, std::string& error);
int64_t append_event(Sqlite& db, Event event);
int64_t record_note(Sqlite& db, const std::string& project, const std::string& kind,
                    const std::string& title, const std::string& body,
                    const std::string& reference = "");
int64_t close_todo(Sqlite& db, int64_t todo_id);
int64_t record_relation(Sqlite& db, const std::string& from, const std::string& to,
                        const std::string& label, const std::string& state);
} // namespace lac
