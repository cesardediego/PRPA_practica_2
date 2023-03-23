import time
import random
from multiprocessing import Lock, Condition, Process
from multiprocessing import Value

SOUTH = 1
NORTH = 0

NCARS = 100
NPED = 10
TIME_CARS = 0.5  # a new car enters each 0.5s
TIME_PED = 5 # a new pedestrian enters each 5s
TIME_IN_BRIDGE_CARS = (1, 0.5) # normal 1s, 0.5s
TIME_IN_BRIDGE_PEDESTRGIAN = (30, 10) # normal 30s, 10s

class Monitor():
    def __init__(self):
        self.mutex = Lock()
        self.patata = Value('i', 0) 
        self.num_coches_norte = Value('i',0) # número de coches que van al norte en el puente
        self.num_coches_sur = Value('i',0) # número de coches que van al sur en el puente
        self.num_peatones = Value('i',0) # número de peatones que van al sur o norte en el puente
        self.norte_coches_esperando = Value('i',0) # número de coches esperando a ir al norte
        self.sur_coches_esperando = Value('i',0) # número de coches esperando a ir al sur
        self.peatones_esperando = Value('i',0) # número de peatones esperando a ir al sur o norte
        self.coches_norte = Condition(self.mutex) # Para indicar que pasan coches al norte
        self.coches_sur = Condition(self.mutex) # Para indicar que pasan cohes al sur
        self.peatones = Condition(self.mutex) # Para indicar que pasan peatones al sur o al norte
        self.turn = Value('i',0) # Para saber a quien le toca pasar. 0 es para indicar que no hay nadie, 1 para los coches del norte, 2 para los coches del sur, 3 para los peatones
        
    def pasa_coche_norte(self):
        return (self.num_coches_sur.value == 0 and self.num_peatones.value == 0) and \
             (self.turn.value == 1) or self.turn.value == 0
    def pasa_coche_sur(self):
        return (self.num_coches_norte.value == 0 and self.num_peatones.value == 0) and \
             (self.turn.value == 2) or self.turn.value == 0
                
    def pasa_peaton(self):
        return (self.num_coches_norte.value == 0 and self.num_coches_sur.value == 0) and \
             (self.turn.value == 3) or self.turn.value == 0
            
    def wants_enter_car(self, direction: int) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        if direction == NORTH:
            self.norte_coches_esperando.value += 1
            self.coches_norte.wait_for(self.pasa_coche_norte)
            self.norte_coches_esperando.value -= 1
            self.turn.value = 1
            self.num_coches_norte.value += 1
        elif direction == SOUTH:
            self.sur_coches_esperando.value += 1
            self.coches_sur.wait_for(self.pasa_coche_sur)
            self.sur_coches_esperando.value -= 1
            self.turn.value = 2
            self.num_coches_sur.value += 1
        self.mutex.release()
                
    def leaves_car(self, direction: int) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        if direction == NORTH:
            self.num_coches_norte.value -= 1
            if self.sur_coches_esperando.value != 0:
                self.turn.value = 2
            elif self.peatones_esperando.value != 0:
                self.turn.value = 3
            else:
                self.turn.value = 0
            if self.num_coches_norte.value == 0:
                self.coches_sur.notify_all()
                self.peatones.notify_all()  
            
        elif direction == SOUTH:
            self.num_coches_sur.value -= 1
            if self.peatones_esperando.value != 0:
                self.turn.value = 3
            elif self.norte_coches_esperando.value != 0:
                self.turn.value = 1
            else:
                self.turn.value = 0
            if self.num_coches_sur.value == 0:
                self.coches_norte.notify_all()
                self.peatones.notify_all()
        self.mutex.release()
    
    def wants_enter_pedestrian(self) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        self.peatones_esperando.value += 1
        self.peatones.wait_for(self.pasa_peaton)
        self.peatones_esperando.value -= 1
        self.turn.value = 3
        self.num_peatones.value += 1
        self.mutex.release()
        
    def leaves_pedestrian(self) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        self.num_peatones.value -= 1
        if self.norte_coches_esperando.value != 0:
            self.turn.value = 1
        elif self.sur_coches_esperando.value != 0:
            self.turn.value = 2
        else:
            self.turn.value = 0
        if self.num_peatones.value == 0:
            self.coches_norte.notify_all()
            self.coches_sur.notify_all()
        self.mutex.release()

    def __repr__(self) -> str:
        return f'Monitor: {self.patata.value}'

def delay_car_north(factor = 5) -> None:
    time.sleep(random.random()/factor)
    
def delay_car_south(factor = 5) -> None:
    time.sleep(random.random()/factor)

def delay_pedestrian(factor = 2) -> None:
    time.sleep(random.random()/factor)

def car(cid: int, direction: int, monitor: Monitor)  -> None:
    print(f"car {cid} heading {direction} wants to enter. {monitor}")
    monitor.wants_enter_car(direction)
    print(f"car {cid} heading {direction} enters the bridge. {monitor}")
    if direction==NORTH :
        delay_car_north()
    else:
        delay_car_south()
    print(f"car {cid} heading {direction} leaving the bridge. {monitor}")
    monitor.leaves_car(direction)
    print(f"car {cid} heading {direction} out of the bridge. {monitor}")

def pedestrian(pid: int, monitor: Monitor) -> None:
    print(f"pedestrian {pid} wants to enter. {monitor}")
    monitor.wants_enter_pedestrian()
    print(f"pedestrian {pid} enters the bridge. {monitor}")
    delay_pedestrian() 
    print(f"pedestrian {pid} leaving the bridge. {monitor}")
    monitor.leaves_pedestrian()
    print(f"pedestrian {pid} out of the bridge. {monitor}")

def gen_pedestrian(monitor: Monitor) -> None: 
    pid = 0
    plst = []
    for _ in range(NPED):
        pid += 1
        p = Process(target=pedestrian, args=(pid, monitor))
        p.start()
        plst.append(p)
        time.sleep(random.expovariate(1/TIME_PED))  

    for p in plst:
        p.join()

def gen_cars(monitor) -> Monitor: 
    cid = 0
    plst = []
    for _ in range(NCARS):
        direction = NORTH if random.randint(0,1)==1  else SOUTH
        cid += 1
        p = Process(target=car, args=(cid, direction, monitor))
        p.start() 
        plst.append(p)
        time.sleep(random.expovariate(1/TIME_CARS))

    for p in plst:
        p.join()

def main():
    monitor = Monitor()
    gcars = Process(target=gen_cars, args=(monitor,))
    gped = Process(target=gen_pedestrian, args=(monitor,))
    gcars.start() 
    gped.start()
    gcars.join()
    gped.join()


if __name__ == '__main__':
    main()
