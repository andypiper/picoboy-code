# from https://codeberg.org/chipfire/rppico-upython
import picoboy
import utime
import time
import framebuf
import random
import math
from machine import PWM, Pin

maxAsteroids = 10

def copyByteArray(src, dest, srcLayout, destLayout, destOffset):
    #print("copyByteArray(" + str(srcLayout) + ", " + str(destLayout) + ", " + str(destOffset) + ")")
    if destOffset[0] % 8 != 0:
        # wir müssen Bytes verschieben :/
        sliceBits = destOffset[0] % 8
        maskL = 0
        for i in range(sliceBits):
            maskL |= 1 << i
        maskH = 0xff ^ maskL
        for y in range(srcLayout[1]):
            destIdx = ((destOffset[1] + y) * (destLayout[0] // 8)) + destOffset[0] // 8
            srcIdx = y * ((srcLayout[0] + 7) // 8)
            #print(str(srcIdx) + " -> " + str(destIdx))
            
            dest[destIdx] |= (src[srcIdx] & maskH) >> sliceBits
            for x in range(((srcLayout[0] + 7) // 8) - 1):
                destIdx = ((destOffset[1] + y) * (destLayout[0] // 8)) + destOffset[0] // 8 + x
                srcIdx = y * ((srcLayout[0] + 7) // 8) + x
                #print(str(x) + " " + str(y) + " -> " + str(srcIdx) + " -> " + str(destIdx))
                
                combinedByte = (src[srcIdx] & maskL) << sliceBits | (src[srcIdx + 1] & maskH) >> sliceBits
                dest[destIdx] |= combinedByte
            destIdx = ((destOffset[1] + y) * (destLayout[0] // 8)) + destOffset[0] // 8
            srcIdx = (y + 1) * ((srcLayout[0] + 7) // 8) - 1
            #print(str(srcIdx) + " -> " + str(destIdx))
            
            dest[destIdx] |= (src[srcIdx] & maskL) << sliceBits
    else:
        # wir können einfach kopieren.
        for y in range(srcLayout[1]):
            for x in range((srcLayout[0] + 7) // 8):
                destIdx = ((destOffset[1] + y) * (destLayout[0] // 8)) + destOffset[0] // 8 + x
                srcIdx = y * ((srcLayout[0] + 7) // 8) + x
                #print(str(x) + " " + str(y) + " -> " + str(srcIdx) + " -> " + str(destIdx))
                dest[destIdx] |= src[srcIdx]

# Parameter:
# src, dest: Ziel- und Quell-Bytearray
# srcOffset, destOffset: x- und y-Koordinate, an die bzw. von der kopiert werden soll
# srcLayout, destLayout: Breite und Höhe von Ziel- und Quellpuffer (in Pixeln -> Bits)
# srcCopyRect: Breite und Höhe des zu kopierenden Bereichs
def andByteArray(src, dest, srcOffset, destOffset, srcLayout, destLayout, srcCopyRect):
    #print("andByteArray(" + str(srcOffset) + ", " + str(destOffset) + ", " + str(srcLayout) + ", " + str(destLayout) + ", " + str(srcCopyRect) + ")")
    
    # zuerst einmal müssen wir alle Zeilen ober- und unterhalb des Bereichs,
    # der manipuliert wird, auf 0 setzen.
    destIdx = 0
    for y in range(destOffset[1]):
        #print("zero line at " + str(destIdx))
        for x in range((destLayout[0] + 7) // 8):
            dest[destIdx] = 0
            destIdx += 1
    destIdx = (destOffset[1] + srcCopyRect[1]) * ((destLayout[0] + 7) // 8)
    for y in range(destLayout[1] - destOffset[1] - srcCopyRect[1]):
        #print("zero line at " + str(destIdx))
        for x in range((destLayout[0] + 7) // 8):
            dest[destIdx] = 0
            destIdx += 1
    
    if (destOffset[0] % 8 != 0) or (srcOffset[0] % 8 != 0):
        # wir müssen Bytes verschieben :/
        # zuerst kopieren wir jede Zeile in einen Zwischenpuffer, so dass Byte 0
        # ein ganzes Byte ist. Das ist weniger verwirrend.
        tempBuffer = bytearray((srcLayout[0] + 7) // 8)
        # um so viele Bits müssen wir jeweils verschieben
        srcSliceBits = srcOffset[0] % 8
        destSliceBits = destOffset[0] % 8
        # Masken anlegen
        srcMaskL = 0
        for i in range(8 - srcSliceBits):
            srcMaskL |= 1 << i
        srcMaskH = 0xff ^ srcMaskL
        destMaskL = 0
        for i in range(8 - destSliceBits):
            destMaskL |= 1 << i
        destMaskH = 0xff ^ destMaskL
        # jetzt kommt die eigentliche Arbeit.
        for y in range(srcCopyRect[1]):
            # zuerst kopieren wir die Quelldaten in den Zwischenpuffer...
            srcIdx = (srcOffset[1] + y) * ((srcLayout[0] + 7) // 8) + (srcOffset[0] // 8)
            #print(str(srcIdx))
            
            if srcOffset[0] % 8 == 0:
                # juhu, der einfach Fall: Die Quelldaten sind an einem Byte ausgerichtet.
                for x in range((srcCopyRect[0] + 7) // 8):
                    tempBuffer[x] = src[srcIdx]
                    srcIdx += 1
            else:
                # hier müssen wir uns die passenden Bytes erst zusammenbauen.                
                tempBuffer[0] = (src[srcIdx] & srcMaskL) << srcSliceBits
                for x in range(((srcCopyRect[0] + 7) // 8) - 1):
                    srcIdx += 1
                    #print(str(srcIdx) + " -> " + str(x))
                    tempBuffer[x] |= (src[srcIdx] & srcMaskH) >> srcSliceBits
                    tempBuffer[x + 1] = (src[srcIdx] & srcMaskL) << srcSliceBits
                
            # jetzt müssen wir nur noch den temporären Buffer in den Zielbuffer übertragen.
            # Das funktioniert genau so wie oben. Der Bereich, den wir kopieren, bleibt
            # allerdings so breit wie die Quelle.
            destIdx = (destOffset[1] + y) * ((destLayout[0] + 7) // 8) + (destOffset[0] // 8)
            #print(str(destIdx))
            
            if destOffset[0] % 8 == 0:
                # juhu, der einfach Fall: Die Quelldaten sind an einem Byte ausgerichtet.
                for x in range((srcCopyRect[0] + 7) // 8):
                    dest[destIdx] &= tempBuffer[x]
                    destIdx += 1
            else:
                # hier müssen wir die Bytes wieder zerlegen. Außerdem müssen wir
                # die Masken andersherum verwenden und fangen mit einem ganzen Byte an.
                # Der obere Teil kommt in das erste Teil-Byte des Zielpuffers.
                dest[destIdx] &= (tempBuffer[0] & destMaskH) >> destSliceBits
                #print(str(destIdx) + " -> " + str(dest[destIdx]))
                
                for x in range(((srcCopyRect[0] + 7) // 8) - 1):
                    destIdx += 1
                    dest[destIdx] &= ((tempBuffer[x] & destMaskL) << destSliceBits) | ((tempBuffer[x + 1] & destMaskH) >> destSliceBits)
                    #print(str(destIdx) + " -> " + str(dest[destIdx]))
            
            # Bereiche links und rechts des zu kopierenden Bereichs auf 0 setzen
            destIdx = (destOffset[1] + y) * ((destLayout[0] + 7) // 8)
            for x in range(((destOffset[0] + 7) // 8) - 1):
                #print("clear " + str(destIdx))
                dest[destIdx] = 0
                destIdx += 1
            destIdx = (destOffset[1] + y) * ((destLayout[0] + 7) // 8) + ((destOffset[0] + srcCopyRect[0] + 7) // 8)
            for x in range((destLayout[0] - destOffset[0] - srcCopyRect[0]) // 8):
                #print("clear " + str(destIdx))
                dest[destIdx] = 0
                destIdx += 1
    else:
        # wir können einfach kopieren.
        for y in range(srcCopyRect[1]):
            srcIdx = (srcOffset[1] + y) * ((srcLayout[0] + 7) // 8)
            destIdx = ((destOffset[1] + y) * (destLayout[0] // 8)) + (destOffset[0] // 8)
            for x in range((srcCopyRect[0] + 7) // 8):
                #print(str(x) + " " + str(y) + " -> " + str(srcIdx) + " -> " + str(destIdx))
                dest[destIdx] &= src[srcIdx]
                srcIdx += 1
                destIdx += 1
            # Bereiche links und rechts des zu kopierenden Bereichs auf 0 setzen
            destIdx = (destOffset[1] + y) * ((destLayout[0] + 7) // 8)
            for x in range(((destOffset[0] + 7) // 8) - 1):
                dest[destIdx] = 0
                destIdx += 1
            destIdx = (destOffset[1] + y) * ((destLayout[0] + 7) // 8) + ((destOffset[0] + srcCopyRect[0] + 7) // 8)
            for x in range((destLayout[0] - destOffset[0] - srcCopyRect[0]) // 8):
                dest[destIdx] = 0
                destIdx += 1

class BoundingBox:
    def __init__(self, pos, size):
        self.up_left = pos
        self.up_right = [pos[0] + size[0] - 1, pos[1]]
        self.down_left = [pos[0], pos[1] + size[1] - 1]
        self.down_right = [pos[0] + size[0] - 1, pos[1] + size[1] - 1]
        self.corners = [self.up_left, self.down_left, self.down_right, self.up_right]
        self.size = size
    
    def changeSize(self, size):
        self.size = size
        self.update()
    
    def update(self):
        self.up_right[0] = self.up_left[0] + self.size[0] - 1
        self.up_right[1] = self.up_left[1]
        self.down_left[0] = self.up_left[0]
        self.down_left[1] = self.up_left[1] + self.size[1] - 1
        self.down_right[0] = self.up_left[0] + self.size[0] - 1
        self.down_right[1] = self.up_left[1] + self.size[1] - 1
    
    def hit(self, point):
        return (point[0] >= self.up_left[0]) and (point[0] < self.up_right[0]) and (point[1] >= self.up_left[1]) and (point[1] < self.down_right[1])
    
    def hitBB(self, other):
        hit = False
        
        for point in self.corners:
            hit |= other.hit(point)
        
        for point in other.corners:
            hit |= self.hit(point)
        
        return hit

class Asteroid:
    # drei Asteroiden, klein, mittel, groß (4x4, 8x6 und 16x13)
    asteroidRaw = [bytearray.fromhex("70d0f060"),
                   bytearray.fromhex("0c7eb7f76e3c"),
                   bytearray.fromhex("0f801ee03bf879ecffa6bff3fff15fef7cff1cc41fc60ffe07f0")]
    # NB I had to fix the pbFrameBuffer values here
    asteroidSprites = [picoboy.pbFrameBuffer(asteroidRaw[0], 4, 4, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(asteroidRaw[1], 8, 6, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(asteroidRaw[2], 16, 13, framebuf.MONO_HLSB)
    ]
        
    asteroidSize = [[4, 4], [8, 6], [16, 13]]
    
    def __init__(self, screen):
        self.vel = [0.0, 0.0]
        self.pos = [-16, -16]
        self.intpos = [0, 0]
        self.size = 0
        self.screen = screen
        self.active = False
        self.bb = BoundingBox(self.intpos, self.asteroidSize[self.size])
        
    def launch(self):
        # Größe zufällig wählen
        self.size = random.randrange(3)
        self.bb.changeSize(self.asteroidSize[self.size])
        
        # zufällige Geschwindigkeit setzen
        self.vel[0] = 0.0
        self.vel[1] = 0.0
        
        while self.vel[0] == 0.0 and self.vel[1] == 0.0:
            self.vel[0] = random.randrange(-4, 5)
            self.vel[1] = random.randrange(-4, 5)
        
        # an zufälliger Position außerhalb des Bildschirms starten
        if self.vel[0] > 0:
            # auf linken 2/3 starten, Asteroid bewegt sich nach rechts
            # X- oder Y-Position zufällig wählen?
            # erst checken, ob Y-Geschwindigkeit != 0
            if self.vel[1] == 0:
                # Asteroid bewegt sich nur in X-Richtung -> Y-Position zufällig wählen
                self.pos[0] = -self.asteroidSprites[self.size].width
                self.pos[1] = random.randrange(-(self.asteroidSprites[self.size].height // 2),
                                               self.screen.height + (self.asteroidSprites[self.size].height // 2))
            elif random.randrange(2) == 0:
                # X-Position
                self.pos[0] = random.randrange(-self.asteroidSprites[self.size].width,
                                               (2 * self.screen.width) // 3)
                
                if self.vel[1] > 0:
                    # oben starten, Asteroid bewegt sich nach unten
                    self.pos[1] = -self.asteroidSprites[self.size].height
                else:
                    # unten starten, Asteroid bewegt sich nach oben
                    self.pos[1] = self.screen.height
            else:
                # Y-Position
                self.pos[0] = -self.asteroidSprites[self.size].width
                
                if self.vel[1] > 0:
                    # oben starten, Asteroid bewegt sich nach unten
                    self.pos[1] = random.randrange(-self.asteroidSprites[self.size].height,
                                                   (2 * self.screen.height) // 3)
                else:
                    # unten starten, Asteroid bewegt sich nach oben
                    self.pos[1] = random.randrange(self.screen.height // 3,
                                                   self.screen.height - self.asteroidSprites[self.size].height)
        elif self.vel[0] < 0:
            # auf rechten 2/3 starten, Asteroid bewegt sich nach links
            # X- oder Y-Position zufällig wählen?
            # erst checken, ob Y-Geschwindigkeit != 0
            if self.vel[1] == 0:
                # Asteroid bewegt sich nur in X-Richtung -> Y-Position zufällig wählen
                self.pos[0] = -self.asteroidSprites[self.size].width
                self.pos[1] = random.randrange(-(self.asteroidSprites[self.size].height // 2),
                                               self.screen.height + (self.asteroidSprites[self.size].height // 2))
            elif random.randrange(2) == 0:
                # X-Position
                self.pos[0] = random.randrange(self.screen.width // 3,
                                               self.screen.width)
                
                if self.vel[1] > 0:
                    # oben starten, Asteroid bewegt sich nach unten
                    self.pos[1] = -self.asteroidSprites[self.size].height
                else:
                    # unten starten, Asteroid bewegt sich nach oben
                    self.pos[1] = self.screen.height
            else:
                # Y-Position
                self.pos[0] = -self.asteroidSprites[self.size].width
                
                if self.vel[1] > 0:
                    # oben starten, Asteroid bewegt sich nach unten
                    self.pos[1] = random.randrange(-self.asteroidSprites[self.size].height,
                                                   (2 * self.screen.height) // 3)
                else:
                    # unten starten, Asteroid bewegt sich nach oben
                    self.pos[1] = random.randrange(self.screen.height // 3,
                                                   self.screen.height - self.asteroidSprites[self.size].height)
        else:
            # Asteroid bewegt sich nicht auf X-Achse
            self.pos[0] = random.randrange(-self.asteroidSprites[self.size].width,
                                           self.screen.width)
            
            if self.vel[1] > 0:
                # oben starten, Asteroid bewegt sich nach unten
                self.pos[1] = -self.asteroidSprites[self.size].height
            else:
                # unten starten, Asteroid bewegt sich nach oben
                self.pos[1] = self.screen.height
        
        self.active = True
    
    def isActive(self):
        return self.active
    
    def move(self):
        if self.active:
            self.pos[0] += self.vel[0]
            self.pos[1] += self.vel[1]
            # brauchen wir, da die Bounding Box auf die Position referenziert!
            # Ohne die Konvertierung bekommt sie für Asteroiden, die zurvor
            # getroffen wurden, Float-Werte! Das selbe Problem haben wir auch
            # beim Blitten.
            self.intpos[0] = int(self.pos[0])
            self.intpos[1] = int(self.pos[1])
            
            # hat der Asteroid den Bildschirm verlassen?
            if self.vel[0] > 0 and self.pos[0] >= self.screen.width:
                self.active = False # nach rechts verschwunden
            elif self.vel[0] < 0 and self.pos[0] <= -self.asteroidSprites[self.size].width:
                self.active = False # nach links verschwunden
            if self.vel[1] > 0 and self.pos[1] >= self.screen.height:
                self.active = False # nach unten verschwunden
            elif self.vel[1] < 0 and self.pos[1] <= -self.asteroidSprites[self.size].height:
                self.active = False # nach oben verschwunden
        if self.active:
            self.bb.update()
    
    def render(self):
        if self.active:
            self.screen.blit(self.asteroidSprites[self.size], self.intpos[0], self.intpos[1], 0)
    
    def destroyed(self):
        if self.size > 0:
            self.size -= 1
            self.bb.changeSize(self.asteroidSize[self.size])
        else:
            self.pos[0] = -16
            self.pos[1] = -16
            self.active = False
    
    def fracture(self, splinter):
        oldvel = self.vel
        self.vel[0] = oldvel[0] * 0.923879533 + oldvel[1] * -0.382683432
        self.vel[1] = oldvel[0] * 0.382683432 + oldvel[1] * 0.923879533
        splinter.vel[0] = oldvel[0] * 0.923879533 + oldvel[1] * 0.382683432
        splinter.vel[1] = oldvel[0] * -0.382683432 + oldvel[1] * 0.923879533
        splinter.pos[0] = self.pos[0]
        splinter.pos[1] = self.pos[1]
        splinter.size = self.size
        splinter.active = True
    
    def getBoundingBox(self):
        return self.bb
    
    def getPixelData(self):
        if self.active:
            return self.asteroidRaw[self.size]
        else:
            return None

class LaserBeam:
    def __init__(self, screen):
        self.screen = screen
        self.active = False
        self.start = [0, 0]
        self.end = [0, 0]
        self.velocity = [0.0, 0.0]
    
    def fire(self, direction, start):
        if direction[0] * direction[1] == 0:
            self.velocity[0] = direction[0] * 10
            self.velocity[1] = direction[1] * 10
        else:
            self.velocity[0] = direction[0] * 7
            self.velocity[1] = direction[1] * 7
        
        self.start = start
        self.end[0] = self.start[0] + self.velocity[0]
        self.end[1] = self.start[1] + self.velocity[1]
        self.active = True
    
    def update(self):
        if self.active:
            self.start[0] = self.end[0]
            self.start[1] = self.end[1]
            self.end[0] += self.velocity[0]
            self.end[1] += self.velocity[1]
            
            if self.start[0] < 0 or self.start[1] < 0 or self.start[0] > self.screen.width or self.start[1] > self.screen.height:
                self.active = False
    
    def render(self):
        if self.active:
            self.screen.line(int(self.start[0]), int(self.start[1]), int(self.end[0]), int(self.end[1]), 1)
    
    def isActive(self):
        return self.active
        
    def checkHit(self, asteroid):
        if self.active and asteroid.isActive():
            bb = asteroid.getBoundingBox()
            
            # Schnittpunkte mit Seitenlinien der Bounding Box berechnen
            if self.velocity[0] != 0:
                s_x0 = (bb.up_left[0] - self.start[0]) / self.velocity[0]
                s_x1 = (bb.up_right[0] - self.start[0]) / self.velocity[0]
            else:
                s_x0 = -1
                s_x1 = -1
            
            if self.velocity[1] != 0:
                s_y0 = (bb.up_left[1] - self.start[1]) / self.velocity[1]
                s_y1 = (bb.down_left[1] - self.start[1]) / self.velocity[1]
            else:
                s_y0 = -1
                s_y1 = -1
            
            # linke Begrenzung (vertikale Linie -> x = const) -> y-Koordinate des Schnitts
            # (x-Koordinate ist ja bekannt)
            intersection_0 = self.start[1] + s_x0 * self.velocity[1]
            # obere Begrenzung (horizontale Linie -> y = const) -> x-Koordinate des Schnitts
            intersection_1 = self.start[0] + s_y0 * self.velocity[0]
            # jetzt noch einmal das selbe für die untere und rechte Begrenzung
            intersection_2 = self.start[1] + s_x1 * self.velocity[1]
            intersection_3 = self.start[0] + s_y1 * self.velocity[0]
            
            # liegen die vertikalen Schnittpunkte im y-Bereich der Bounding Box?
            i0 = (intersection_0 >= bb.up_left[1]) and (intersection_0 < bb.down_left[1]) and (s_x0 <= 1.0) and (s_x0 >= 0)
            i2 = (intersection_2 >= bb.up_left[1]) and (intersection_2 < bb.down_left[1]) and (s_x1 <= 1.0) and (s_x1 >= 0)
            # liegen die hoizontalen Schnittpunkte im x-Bereich der Bounding Box?
            i1 = (intersection_1 >= bb.up_left[0]) and (intersection_1 < bb.up_right[0]) and (s_y0 <= 1.0) and (s_y0 >= 0)
            i3 = (intersection_3 >= bb.up_left[0]) and (intersection_3 < bb.up_right[0]) and (s_y1 <= 1.0) and (s_y1 >= 0)
            
            if i0 or i1 or i2 or i3:
                self.active = False
                asteroid.destroyed()
                return asteroid
            else:
                return None

class Spaceship():
    spaceshipRaw = [[bytearray.fromhex("0000000000000000018003c0066006600ff00ff00bd00a500000000000000000"),
                bytearray.fromhex("0000000000000000018003c0066006600ff00ff00bd00a500180024001800180")],
                [bytearray.fromhex("00000000000000000fc00de009d00fc00fe00f80048002000000000000000000"),
                bytearray.fromhex("00000000000000000fc00de009d00fc00fe00fa004e002180018000000000000")],
                [bytearray.fromhex("000000000000000000f003c007f00ce00ce007f003c000f00000000000000000"),
                bytearray.fromhex("000000000000000000f003c007f40ceb0ceb07f403c000f00000000000000000")],
                [bytearray.fromhex("00000000000000000000020004800f800fe00fc009d00de00fc0000000000000"),
                bytearray.fromhex("00000000000000000018021804e00fa00fe00fc009d00de00fc0000000000000")],
                [bytearray.fromhex("00000000000000000a500bd00ff00ff00660066003c001800000000000000000"),
                bytearray.fromhex("01800180024001800a500bd00ff00ff00660066003c001800000000000000000")],
                [bytearray.fromhex("000000000000000000000040012001f007f003f00b9007b003f0000000000000"),
                bytearray.fromhex("000000000000000018001840072005f007f003f00b9007b003f0000000000000")],
                [bytearray.fromhex("00000000000000000f0003c00fe0073007300fe003c00f000000000000000000"),
                bytearray.fromhex("00000000000000000f0003c02fe0d730d7302fe003c00f000000000000000000")],
                [bytearray.fromhex("000000000000000003f007b00b9003f007f001f0012000400000000000000000"),
                bytearray.fromhex("000000000000000003f007b00b9003f007f005f0072018401800000000000000")]
                ]
    spaceship = [[picoboy.pbFrameBuffer(spaceshipRaw[0][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[0][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[1][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[1][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[2][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[2][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[3][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[3][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[4][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[4][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[5][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[5][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[6][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[6][1], 16, 16, framebuf.MONO_HLSB)],
             [picoboy.pbFrameBuffer(spaceshipRaw[7][0], 16, 16, framebuf.MONO_HLSB),
             picoboy.pbFrameBuffer(spaceshipRaw[7][1], 16, 16, framebuf.MONO_HLSB)]
             ]
    
    collisionBuffer = bytearray(16 * (16 // 8))
    
    def __init__(self, screen, pos, boundary):
        self.screen = screen
        self.pos = pos
        self.boundary = boundary
        self.vel = [0, 0]
        self.animation = 0
        self.orientation = 0
        self.bb = BoundingBox(self.pos, [16, 16])
        
    def move(self):
        self.pos[0] += self.vel[0]
        self.pos[1] += self.vel[1]
        
        if self.pos[0] < self.boundary[0][0]:
            self.pos[0] = self.boundary[0][0]
        elif self.pos[0] > self.boundary[0][1]:
            self.pos[0] = self.boundary[0][1]
        
        if self.pos[1] < self.boundary[1][0]:
            self.pos[1] = self.boundary[1][0]
        elif self.pos[1] > self.boundary[1][1]:
            self.pos[1] = self.boundary[1][1]
        
        self.bb.update()
    
    def setXVelocity(self, v):
        self.vel[0] = v
    
    def setYVelocity(self, v):
        self.vel[1] = v
    
    def rotateLeft(self):
        self.orientation += 1
        
        if self.orientation >= len(self.spaceship):
            self.orientation = 0
    
    def rotateRight(self):
        self.orientation -= 1
        
        if self.orientation < 0:
            self.orientation = len(self.spaceship) - 1
    
    def checkCollision(self, asteroid):
        collision = False
        
        if asteroid.isActive():
            aBB = asteroid.getBoundingBox()
            
            # zunächst über die Bounding Boxes auf eine mögliche Kollision prüfen
            if self.bb.hitBB(aBB):
                # Feld für Kollisionstest mit aktuellem Raumschiff füllen
                for i in range(len(self.collisionBuffer)):
                    self.collisionBuffer[i] = self.spaceshipRaw[self.orientation][0][i]
                
                asteroidOffset = [asteroid.intpos[0] - self.pos[0], asteroid.intpos[1] - self.pos[1]]
                #print("collision detection: aBB " + str(aBB) + " offset " + str(asteroidOffset))
                #src, dest, srcOffset, destOffset, srcLayout, destLayout, srcCopyRect
                # jetzt den Asteroiden damit verUNDen
                if asteroidOffset[0] >= 0:
                    if asteroidOffset[1] >= 0:
                        # x- und y-Position des Asteroiden sind größer -> wir kopieren ihn von [0, 0] bis [15 - aX, 15 - aY]
                        #print("collision detection: P0")
                        copyWidth = [min(16 - asteroidOffset[0], aBB.size[0]), min(16 - asteroidOffset[1], aBB.size[1])]
                        andByteArray(asteroid.getPixelData(), self.collisionBuffer, [0, 0], asteroidOffset, aBB.size, [16, 16], copyWidth)
                    else:
                        # y-Position des Asteroiden ist kleiner -> wir kopieren ihn von [0, -aY] bis [15 - aX, wY - 1]
                        #print("collision detection: P1")
                        copyWidth = [min(16 - asteroidOffset[0], aBB.size[0]), aBB.size[1] + asteroidOffset[1]]
                        andByteArray(asteroid.getPixelData(), self.collisionBuffer, [0, -asteroidOffset[1]], [asteroidOffset[0], 0], aBB.size, [16, 16], copyWidth)
                else:
                    if asteroidOffset[1] < 0:
                        # x- und y-Position des Asteroiden sind kleiner -> wir kopieren ihn von [-aX, -aY] bis [wX - 1, xY - 1]
                        #print("collision detection: P2")
                        copyWidth = [aBB.size[0] + asteroidOffset[0], aBB.size[1] + asteroidOffset[1]]
                        andByteArray(asteroid.getPixelData(), self.collisionBuffer, [-asteroidOffset[0], -asteroidOffset[1]], [0, 0], aBB.size, [16, 16], copyWidth)
                    else:
                        # x-Position des Asteroiden ist kleiner -> wir kopieren ihn von [-oX, 0] bis [wX - 1, 15 - aY]
                        #print("collision detection: P3")
                        copyWidth = [aBB.size[0] + asteroidOffset[0], min(16 - asteroidOffset[1], aBB.size[1])]
                        andByteArray(asteroid.getPixelData(), self.collisionBuffer, [-asteroidOffset[0], 0], [0, asteroidOffset[1]], aBB.size, [16, 16], copyWidth)
            
                for i in range(len(self.collisionBuffer)):
                    collision |= self.collisionBuffer[i] != 0
        
        return collision
    
    def render(self, blink = False):
        if not blink or (blink and (self.animation // 2) == 0):
            self.screen.blit(self.spaceship[self.orientation][self.animation // 5], self.pos[0], self.pos[1], 0)
        self.animation += 1
        
        if self.animation >= 10:
            self.animation = 0

splashscreenRaw = bytearray.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000f8000000000000000000000000000000fc000000000000000000000000000000cd800000000000000000000000000000cd9e1c00000000000000000000000000fc3f3e00000000000000000000000000f9b36300000000000000000000000000c1b06300000000000000000000000000c1b36300000000000000000000000000c1bf3e00000000000000000000000000c19e1c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000180000000006000000000000000018003c000000000f00000000000000003c003c000000000f00000e0000000000180038000000001f00001c0000000000000038000000003f00001c0000000000000078000000003f01f87f83e06707c0301e70fc0000007f03fdff07f0ef1fe0783f71fe0000007707fcfe0f70fe1ff0787ff3fe000000f70718701e30f83cf070f3e38c000000e70700703c70f0787871e1e3c0000001e78700703ff0e0787871c1e3e0000001ff8780f03fe1e07078f1c1e1f0000003ff83e0f07f01e0f078f1c1e0f8000003ff81f0e07001c0f070f3c3e07c0000078380f8e07801c0f070e3c3e03c000007838078e07831c0f070e3c7c01e00000f0388f8e33c73c079e1e3ffc43e00000f039ff0fe3fe3c07fe1e1ffcffe00001e03dff07e1fe3803fc1e1f9cff800001c01cfc03c0f81801f01c0f187e000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003000000000180000000000000000000078780000001863000000000000000000fc7d8000001863600000000cc0000001fe6d8000001877600000001ec0000001327d8f3300997f073673ccdec1cd800030799f3300ff6b6fbefbecccf3efc00030619b33007e636c38db6cccfb6ec0003061df1f003c636fb0fbe7cedbecc0003060ce8e001863673073c386d9ccc000000000060000000000030180000000000000000c000000000003030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000")

#########################################
# main()								#
#########################################
db = Pin(5, Pin.OUT)
db.on()

pb = picoboy.PicoBoy()
leds = [pb.LED_RED, pb.LED_YELLOW, pb.LED_GREEN]
speaker = PWM(pb.SPEAKER)

pb.init_display()

# alles, was das Spiel braucht, wird zu Beginn angelegt, um möglichst wenig dynamischen
# Speicher zu benötigen.
splashscreen = picoboy.pbFrameBuffer(splashscreenRaw, 128, 64, framebuf.MONO_HLSB)
    
asteroids = [Asteroid(pb) for i in range(4*maxAsteroids)]
lb = [LaserBeam(pb), LaserBeam(pb), LaserBeam(pb), LaserBeam(pb)]
ship = Spaceship(pb, [(pb.width // 2) - 8, (pb.height // 2) - 8], [[-4, pb.width - 12], [-4, pb.height - 12]])

# Ausrichtung des Schiffs in x- und y-Richtung
orientationToHeading = [[0, -1], [-1, -1], [-1, 0], [-1, 1], [0, 1], [1, 1], [1, 0], [1, -1]]

soundFreq = [200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000]
explosionSamples = [150, 125, 100]
shipHitSamples = [600, 200, 600, 200, 600, 200]

zeroPos = [pb.yAcc(), pb.xAcc(), pb.zAcc()]

finish = False
rngSeeded = False

while not finish:
    for led in leds:
        led.off()
    
    speaker.duty_u16(0)
    
    #pb.text("UP: start", 0, 16)
    #pb.text("DOWN: upython", 0, 32)
    pb.blit(splashscreen, 0, 0)
    pb.show()
    
    while True:
        if pb.pressedUp():
            break
        if pb.pressedDown():
            finish = True
            break
    
    if finish:
        pb.fill(0)
        pb.text("Goodbye!", 0, 32)
        pb.show()
        break

    animation = 0
    orientation = 0
    velocity = [0, 0]
    explosionOff = len(explosionSamples)
    shipHitOff = len(shipHitSamples)
    soundLaser = False

    cooldown = 3
    lives = 3
    reviveTimeout = 10
    dead = False
    soundOff = 0
    ship.pos[0] = (pb.width // 2) - 8
    ship.pos[1] = (pb.height // 2) - 8
    
    # wir brauchen einen möglichst zufälligen Startwert für den Zufallszahlengenerator.
    # Da bietet sich der Beschleunigungssensor an. Die Zahlen, mit denen hier multipliziert wird,
    # haben keinen tieferen Sinn, sie sollen einfach nur einen möglichst großen Wertebereich abdecken.
    if not rngSeeded:
        random.seed(int(pb.yAcc() * 33554431 +  pb.xAcc() * 655535 + pb.zAcc() * 1023))

    while not dead:
        # Zeit speichern, um alle Frames möglichst 100 ms lang zu bekommen
        timeStart = time.ticks_ms()
        
        # wird ein Sound abgespielt? Falls ja: passendes Sample laden.
        if shipHitOff < len(shipHitSamples):
            speaker.duty_u16(32768)
            speaker.freq(shipHitSamples[shipHitOff])
            shipHitOff += 1
        elif soundLaser:
            speaker.duty_u16(32768)
            speaker.freq(1000)
            soundLaser = False
        elif explosionOff < len(explosionSamples):
            speaker.duty_u16(32768)
            speaker.freq(explosionSamples[explosionOff])
            explosionOff += 1
        else:
            speaker.duty_u16(0)# wenn nicht: Lautsprecher aus
        
        if soundOff >= len(soundFreq):
            soundOff = 0
        
        # LEDs zeigen die verbleibenden Leben an, entsprechend viele einschalten
        for led in leds[:lives]:
            led.on()
        for led in leds[lives:]:
            led.off()
        
        # lange Seite des Displays ist y-Achse
        currPos = [pb.yAcc(), pb.xAcc(), 0]
        
        # Bewegungssteuerung des Schiffs
        if currPos[0] - zeroPos[0] < -0.1:
            if currPos[0] - zeroPos[0] < -0.2:
                ship.setXVelocity(2)
            else:
                ship.setXVelocity(1)
        elif currPos[0] - zeroPos[0] > 0.1:
            if currPos[0] - zeroPos[0] > 0.2:
                ship.setXVelocity(-2)
            else:
                ship.setXVelocity(-1)
        else:
            ship.setXVelocity(0)
        
        if currPos[1] - zeroPos[1] < -0.1:
            if currPos[1] - zeroPos[1] < -0.2:
                ship.setYVelocity(-2)
            else:
                ship.setYVelocity(-1)
        elif currPos[1] - zeroPos[1] > 0.1:
            if currPos[1] - zeroPos[1] > 0.2:
                ship.setYVelocity(2)
            else:
                ship.setYVelocity(1)
        else:
            ship.setYVelocity(0)
        
        # Schiff bewegen, Bildschirm leeren und anzeigen
        ship.move()
        
        pb.fill(0)
        ship.render(reviveTimeout > 0)
        
        # Zähler für Animation des Schiffs
        animation += 1
        if animation >= 10:
            animation = 0
        
        # Buttons abfragen
        if pb.pressedLeft():
            ship.rotateLeft()
        elif pb.pressedRight():
            ship.rotateRight()

        cooldown -= 1

        # Laser abfeuern?
        if pb.pressedCenter():
            if cooldown <= 0:
                for beam in lb:
                    if not beam.isActive():
                        beam.fire(orientationToHeading[ship.orientation], [ship.pos[0] + 8, ship.pos[1] + 8])
                        cooldown = 3# nach jedem Schuss 3 Frames warten
                        soundLaser = True
                        break
        
        # einen neuen Asteroiden starten?
        if(random.randrange(20) == 0):
            # ersten inaktiven Asteroiden finden und starten.
            # Neue Asteroiden werden nur im ersten Viertel angelegt,
            # um genug Platz für Bruchstücke zu haben.
            for a in asteroids[:maxAsteroids]:
                if not a.isActive():
                    a.launch()
                    break

        # zuerst alle Asteroiden updaten...
        for a in asteroids:
            a.move()
        # ... prüfen, ob ein Laserstrahl sie getroffen hat,...
        for a in asteroids:
            for beam in lb:
                splintered = beam.checkHit(a)
                if splintered != None:
                    explosionOff = 0
                    if splintered.isActive():
                        for s in asteroids[maxAsteroids:]:
                            if not s.isActive():
                                splintered.fracture(s)
                                break
        # ...dann zeichnen. Das verhindert, dass neue Fragmente nicht
        # bewegt werden, weil sie vor dem Ursprungsfragment eingefügt wurden.
        collision = False
        for a in asteroids:
            if reviveTimeout <= 0:
                collision |= ship.checkCollision(a)
            a.render()
        
        # Zähler für Unverwundbarkeit zu Beginn eines Spiels und nach einem Asteroidentreffer
        if reviveTimeout > 0:
                reviveTimeout -= 1
        
        # hat ein Asteroid das Raumschiff getroffen?
        if collision:
            shipHitOff = 0
            lives -= 1
            if lives <= 0:
                dead = True
            reviveTimeout = 10
        
        for beam in lb:
            beam.render()
            beam.update()

        # jetzt den neuen Bildschirminhalt anzeigen
        pb.show()
        
        # Zeit auslesen und warten, bis der Frame 100 ms gedauert hat.
        timeNow = time.ticks_ms()

        time.sleep_ms(100 - (timeNow - timeStart))