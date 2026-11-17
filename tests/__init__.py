import atexit
import os
import shutil
import tempfile

TEST_DIR = tempfile.mkdtemp(prefix="localrevisor-tests-")
os.environ["LOCALREVISOR_DATA_DIR"] = TEST_DIR
os.environ["LOCALREVISOR_ENV_PATH"] = os.path.join(TEST_DIR, ".env")
os.environ.pop("OPENAI_API_KEY", None)


@atexit.register
def _cleanup():
    shutil.rmtree(TEST_DIR, ignore_errors=True)
