#pragma once
#include "lac/core.hpp"
namespace lac {
std::string integration_request(const fs::path& helper, const fs::path& config,
                                const std::string& action, const std::string& params,
                                bool private_input = false);
}
