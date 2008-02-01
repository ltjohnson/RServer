#!/bin/sh
LD_LIBRARY_PATH="/usr/lib/R/lib" "exec" "python" "rserver.py" "$*"
del LD_LIBRARY_PATH
