import importlib
import pkgutil
from logging import getLogger
from pathlib import Path
from types import ModuleType
from typing import Type, Union

import discord
from discord.ext import commands

logger = getLogger(__name__)


class NorthIsBot(commands.Bot):
    async def on_ready(self) -> None:
        logger.debug("Logged on as {0}!".format(self.user))

    def discover_extensions(self, path: Union[Path, str]):
        """load all cogs under path"""
        path = Path(path)

        for location in [path / "apps"]:
            if not location.exists():
                continue

            for (module_loader, name, ispkg) in pkgutil.iter_modules([location]):
                mod = importlib.import_module(f"{path.name}.{location.name}.{name}")
                print(module_loader, name, ispkg)
                for name in dir(mod):
                    loadable = getattr(mod, name, None)
                    if name.startswith("_") or isinstance(loadable, ModuleType):
                        continue
                    if isinstance(loadable, commands.Cog):
                        logger.info(
                            f"discovred Cog instance {loadable.__name__}@{repr(loadable)}"
                        )
                        self.add_cog(loadable)
                    elif isinstance(loadable, type) and issubclass(
                        loadable, commands.Cog
                    ):
                        logger.info(
                            f"discovred Cog class {loadable.__name__}@{repr(loadable)}"
                        )
                        self.add_cog(loadable(self))
                    elif isinstance(loadable, commands.Command):
                        logger.info(f"discovred Command {loadable}@{repr(loadable)}")
                        self.add_command(loadable)
                    else:
                        logger.debug(f"skipping {name}")

        # all_my_base_classes = {
        #     cls.__name__: cls for cls in base._MyBase.__subclasses__()
        # }

        # for module in chain(
        #     [_.basename() for _ in path.glob("cogs/*.py")],
        #     [_.parent for _ in path.glob("cogs/*/__init__.py")],
        # ):
        #     imported_mod = __import__(module)
        #     for attr in dir(imported_mod):
        #         maybe_command = getattr(imported_mod, attr, None)
        #         if isinstance(maybe_command, discoverable_types):
        #             self.add_command(maybe_command)

    async def send_message(
        self, message: discord.Message, response: str, img_url: str = None
    ):
        for small_response in (r.strip() for r in response.split("\n\n") if r.strip()):
            await message.channel.trigger_typing()
            await message.channel.send(small_response)
        if img_url:
            await message.channel.trigger_typing()
            await message.channel.send(img_url)
