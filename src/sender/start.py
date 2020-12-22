import os

cmd = "gunicorn -b 0.0.0.0:5000 --chdir /src main:app"

returned_value = os.system(cmd)  # returns the exit code in unix
print('returned value:', returned_value)
