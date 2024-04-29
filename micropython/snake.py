# from the website
from picoboy import PicoBoy
import time
import random

xSize = 29
ySize = 15
pb = PicoBoy()
board = [[0 for x in range(ySize)] for y in range(xSize)]

##### Quellcode ueber dieser Linie bitte nicht aendern! #####

laenge=3
xPos=14
yPos=7
richtung = random.randint(1,4)

def putApple():
    global board
    x = random.randint(0,xSize-1)
    y =  random.randint(0,ySize-1)
    while(board[x][y] != 0):
        x =  random.randint(0,xSize-1)
        y =  random.randint(0,ySize-1)
    board[x][y] = -1

def erlaubt(x,y):
    if x<0 or x>=xSize or y<0 or y>=ySize or board[x][y] > 0:
        return False
    else:
        return True


def spielfeldLeeren():
    global board
    i = 0
    while i < xSize:
        j = 0
        while j < ySize:
          board[i][j] = 0
          j = j + 1
        i = i + 1

def score():
    global laenge
    punkte = laenge - 3
    pb.text(str(punkte%10),120,43,1)
    punkte = int(punkte/10)
    pb.text(str(punkte%10),120,33,1)
    punkte = int(punkte/10)
    pb.text(str(punkte%10),120,23,1)
    punkte = int(punkte/10)

def spielfeldZeichnen():
    global xPos
    global yPos
    global board
    global laenge
    score()
    pb.rect(0,0,4*(xSize+1),4*(ySize+1),1)
    i = 0
    while i < xSize:
        j = 0
        while j < ySize:
            if board[i][j] > 0:
                if board[i][j] == laenge:
                    pb.fill_rect(i*4+2,j*4+2,4,4,1)
                else:
                    pb.rect(i*4+2,j*4+2,4,4,1)
                board[i][j] = board[i][j] - 1
            if board[i][j] == -1:
                pb.fill_rect(i*4+3,j*4+3,2,2,1)
            j = j + 1
        i = i + 1

def schritt():
    global xPos
    global yPos
    global board
    global richtung
    global laenge
    
    if (pb.pressedUp() and richtung != 2):
        richtung = 1
    if (pb.pressedDown() and richtung != 1):
        richtung = 2
    if (pb.pressedLeft()and richtung != 4):
        richtung = 3
    if (pb.pressedRight()and richtung != 3):
        richtung = 4
        
    if richtung == 1:
        yPos = yPos - 1
    if richtung == 2:
        yPos = yPos + 1
    if richtung == 3:
        xPos = xPos - 1
    if richtung == 4:
        xPos = xPos + 1
        
    if(not erlaubt(xPos,yPos)):
        while(True):
            pb.fill_rect(10,10,4*(xSize+1)-20,4*(ySize+1)-20,0)
            pb.rect(10,10,4*(xSize+1)-20,4*(ySize+1)-20,1)
            pb.text("Score:",18,18)
            pb.text(str(laenge - 3),18,28)
            pb.show()
            time.sleep_ms(4000)
            machine.reset()
            
    if(board[xPos][yPos] == -1):
        laenge = laenge + 1
        putApple()
        
    board[xPos][yPos] = laenge

spielfeldLeeren()
putApple()

last = time.ticks_us()

while True :
    schritt()
    pb.fill(0)
    spielfeldZeichnen()
    pb.show()
    
    while time.ticks_diff(time.ticks_us(), last) < 75000:
        pass
    last = time.ticks_us()