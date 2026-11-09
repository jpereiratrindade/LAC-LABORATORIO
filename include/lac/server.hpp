#pragma once
#include "lac/core.hpp"
namespace lac {
void serve(Sqlite& db, int port, int scan_every, const fs::path& web_root,
           const fs::path& integration_helper, const fs::path& integration_config,
           const std::string& bind_address = "127.0.0.1", const std::string& token = "");
}
