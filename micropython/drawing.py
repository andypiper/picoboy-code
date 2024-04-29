# from the tutorial
from picoboy import PicoBoy
import random

pb = PicoBoy()

xPos = 64
yPos = 32
gamerunning = 1

while True:
  if(pb.pressedUp() and yPos > 0): # Joystick pressed up?
    yPos = yPos - 1 # Verringere Variable yPos um 1
  if(pb.pressedDown() and yPos < 63): # Joystick pressed down?
    yPos = yPos + 1 # Increase variable yPos by 1
  if(pb.pressedLeft() and xPos > 0): # Joystick pressed to the left?
    xPos = xPos - 1 # Verringere Variable xPos a 1
  if(pb.pressedRight() and xPos < 127): # Joystick pressed to the right?
    xPos = xPos + 1 # Increase variable xPos by 1
  if(pb.pressedCenter()): # Joystick pressed in the middle?
    pb.fill(0) # Empty image memory

  pb.pixel(xPos,yPos,1) # Draw pixels at position (xPos,yPos) into the image memory
  pb.show() # Show image buffer
  pb.delay(20)                                  # 20 ms warten