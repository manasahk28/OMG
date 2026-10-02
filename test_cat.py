import time
from cat_popup import CatPopup

print("Showing cat popup on screen...")
p = CatPopup()
p.show("Hey there! 🐾\nI am right here!", duration=5.0)
print("Cat is displayed in the bottom-right corner for 5 seconds!")
time.sleep(5.5)
print("Test completed successfully.")
