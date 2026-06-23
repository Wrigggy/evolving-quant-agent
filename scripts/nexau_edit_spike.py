import os, sys, pathlib
REPO=pathlib.Path("/Users/kevinwu/Coding/evolving-quant-agent")
WORKER=REPO/"qea"/"worker_gdpval"
sys.path.insert(0,str(REPO))
for line in (REPO/".env").read_text().splitlines():
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,_,v=line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LLM_API_KEY"]=os.environ.get("OPENROUTER_API_KEY",""); os.environ["LLM_BASE_URL"]=os.environ.get("OPENROUTER_BASE_URL","https://openrouter.ai/api/v1"); os.environ.setdefault("LLM_MODEL","deepseek/deepseek-v4-pro")
from nexau import Agent, AgentConfig
agent=Agent(config=AgentConfig.from_yaml(config_path=WORKER/"agent.yaml"))
wd=pathlib.Path(agent.sandbox_manager.instance.work_dir)
# simulate a harness file (a tool .py) placed in the editable dir
target=wd/"a_tool.py"
target.write_text("def my_tool(x):\n    return x  # original\n")
before=target.read_text()
ctx={"date":"2026-06-23","username":os.environ.get("USER","kevin"),"working_directory":str(wd)}; ctx["env_content"]=dict(ctx)
agent.run(message="Using the shell tool, edit the file a_tool.py in your working directory: add a new function `def added_by_evolve(): return 42` at the end. Then print the file contents.", context=ctx)
after=target.read_text()
print("=== BEFORE ===\n"+before)
print("=== AFTER ===\n"+after)
print("EDIT SUCCEEDED:", "added_by_evolve" in after and after!=before)
