#include "lac/integrations.hpp"
#include <array>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <poll.h>
#include <stdexcept>
#include <sys/wait.h>
#include <unistd.h>

namespace lac {
std::string integration_request(const fs::path& helper,const fs::path& config,
                                const std::string& action,const std::string& params){
  if(!fs::is_regular_file(helper))throw std::runtime_error("integration helper missing");
  const std::string script=helper.string(),file=config.string();
  int fds[2];if(pipe(fds)!=0)throw std::runtime_error("integration pipe failed");
  const pid_t pid=fork();
  if(pid<0){close(fds[0]);close(fds[1]);throw std::runtime_error("integration fork failed");}
  if(pid==0){
    setpgid(0,0);
    dup2(fds[1],STDOUT_FILENO);close(fds[0]);close(fds[1]);
    const char* args[]={"python3",script.c_str(),"--config",file.c_str(),"--action",action.c_str(),
                        "--params",params.c_str(),nullptr};
    execvp("python3",const_cast<char* const*>(args));_exit(127);
  }
  setpgid(pid,pid);close(fds[1]);
  const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(8);
  std::string result;std::array<char,8192> chunk{};bool failed=false;
  while(true){
    if(std::chrono::steady_clock::now()>=deadline){failed=true;break;}
    pollfd input{fds[0],POLLIN,0};const int ready=poll(&input,1,100);
    if(ready<0){if(errno==EINTR)continue;failed=true;break;}
    if(!ready)continue;
    const ssize_t n=read(fds[0],chunk.data(),chunk.size());
    if(n==0)break;
    if(n<0){if(errno==EINTR)continue;failed=true;break;}
    result.append(chunk.data(),static_cast<size_t>(n));
    if(result.size()>(1U<<20)){failed=true;break;}
  }
  close(fds[0]);int status=0;
  // Reap with a deadline even if a child closed stdout but did not exit.
  while(waitpid(pid,&status,WNOHANG)==0){
    if(failed||std::chrono::steady_clock::now()>=deadline){
      failed=true;kill(-pid,SIGKILL);kill(pid,SIGKILL);
      while(waitpid(pid,&status,0)<0&&errno==EINTR){}break;
    }
    poll(nullptr,0,10);
  }
  if(failed||!WIFEXITED(status)||WEXITSTATUS(status)!=0||result.empty())
    throw std::runtime_error("integration unavailable, timed out or exceeded response limit");
  return result;
}
}
