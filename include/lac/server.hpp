#pragma once
#include "lac/core.hpp"
namespace lac {
void serve(Sqlite& db, int port, int scan_every, const fs::path& web_root);
}
