from pathlib import Path
from pydantic import TypeAdapter
from eamis_sys import EamisCatcher
from eamis_sys.api import FullData as EamisFullData

HERE = Path(__file__).parent
EamisFullDataValidator = TypeAdapter(EamisFullData)

client = EamisCatcher.from_account(input('username:'), input('password:'))
snapshot = client.full_data()

(HERE / 'eamis_snapshot.json') \
    .write_bytes(EamisFullDataValidator.dump_json(snapshot, indent=4))
