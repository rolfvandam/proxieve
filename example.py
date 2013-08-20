import re
import time

from Proxy import Proxy

p = Proxy()
p.startProxy()

# Outputs all jpg urls that it encounters.
def hook(message):
     urls = re.findall('["\'][^"\']+\.jpe?g["\']', message)
     if urls:
            print urls
    
p.setHook(hook)

# Wait around forever to see the results
while True:
    time.sleep(1000)
