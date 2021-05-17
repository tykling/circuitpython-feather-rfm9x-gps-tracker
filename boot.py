import storage
# make storage writable from circuitpython
# to make the feather writable again:
#     import os
#     os.rename("/boot.py", "/boot.py.bak")
# and reset the feather
storage.remount("/", False)

