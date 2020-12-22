import os

cmd = "python3 -u /src/main.py"

returned_value = os.system(cmd)  # returns the exit code in unix
print('returned value:', returned_value)
