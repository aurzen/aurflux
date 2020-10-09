from __future__ import annotations

import typing as ty

if ty.TYPE_CHECKING:
   from .context import ConfigCtx

import yaml
import pathlib as pl
import collections as clc
import contextlib
import asyncio.locks
import aurcore

CONFIG_DIR = pl.Path("./.fluxconf/")
CONFIG_DIR.mkdir(exist_ok=True)

CACHED_CONFIGS = 100


# @ext.AutoRepr
class Config(metaclass=aurcore.util.Singleton):

   def __init__(self, admin_id, name=""):
      self.config_dir = CONFIG_DIR / name
      self.config_dir.mkdir(exist_ok=True)
      if not (self.config_dir / "base.yaml").exists():
         with (self.config_dir / "base.yaml").open("w") as f:
            yaml.safe_dump({
               "prefix"  : "..",
               "admin_id": admin_id,
               "auths"   : {}}
               , f)

      with (self.config_dir / "base.yaml").open("r") as f:
         self.base_config = yaml.safe_load(f)
      self.cached: clc.OrderedDict = clc.OrderedDict()
      self.locks: ty.Dict[str, asyncio.locks.Lock] = clc.defaultdict(asyncio.locks.Lock)

   def _write_config_file(self, config_id: str, data):
      local_config_path: pl.Path = self.config_dir / f"{config_id}.yaml"
      with local_config_path.open("w") as f:
         yaml.safe_dump(data, f)

   def _load_config_file(self, config_id: str):
      local_config_path: pl.Path = self.config_dir / f"{config_id}.yaml"
      try:
         with local_config_path.open("r") as f:
            local_config = yaml.safe_load(f)
      except FileNotFoundError:
         local_config = {}
      return local_config

   def of(self, identifiable: ConfigCtx) -> ty.Dict[str, ty.Any]:
      identifier = identifiable.config_identifier
      if identifier in self.cached:
         self.cached.move_to_end(identifier, last=False)
         configs = self.cached[identifier]
      else:
         local_config = self._load_config_file(identifier)
         combined_dict = {**self.base_config, **local_config}
         cleaned_dict = {k: combined_dict[k] for k in self.base_config}
         if cleaned_dict != local_config:
            self._write_config_file(identifier, cleaned_dict)

         self.cached[identifier] = cleaned_dict
         if len(self.cached) > CACHED_CONFIGS:
            self.cached.popitem()

         configs = cleaned_dict

      return configs


   @contextlib.asynccontextmanager
   async def writeable_conf(self, identifiable: ConfigCtx):
      config_id = identifiable.config_identifier
      async with self.locks[config_id]:
         output_dict = self.of(identifiable)
         try:
            yield output_dict
         finally:
            self._write_config_file(config_id, output_dict)
            self.cached[config_id] = output_dict
