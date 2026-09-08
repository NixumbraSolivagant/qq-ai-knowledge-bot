import nonebot
from dotenv import load_dotenv
from nonebot.adapters.onebot.v11 import Adapter
from pathlib import Path

load_dotenv(Path(__file__).with_name(".env"))
nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(Adapter)
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()
