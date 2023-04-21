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
        
    def pasa_coche_norte(self): # Condiciones para que pueda pasar coche al norte : no hay coches pasando al sur ni peatones y es el turno 1 o 0
        return (self.num_coches_sur.value == 0 and self.num_peatones.value == 0) and \
             (self.turn.value == 1) or self.turn.value == 0
    def pasa_coche_sur(self): # Condiciones para que pueda pasar coche al sur : no hay coches pasando al norte ni peatones y es el turno 2 o 0
        return (self.num_coches_norte.value == 0 and self.num_peatones.value == 0) and \
             (self.turn.value == 2) or self.turn.value == 0
                
    def pasa_peaton(self):# Condiciones para que pueda pasar peaton : no hay coches pasando al norte ni al sur y es el turno 3 o 0
        return (self.num_coches_norte.value == 0 and self.num_coches_sur.value == 0) and \
             (self.turn.value == 3) or self.turn.value == 0
            
    def wants_enter_car(self, direction: int) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        if direction == NORTH:
            self.norte_coches_esperando.value += 1 # sumamos uno a los coches esperando para el norte
            self.coches_norte.wait_for(self.pasa_coche_norte) # Esperamos  a que pueda pasar el coche al norte
            self.norte_coches_esperando.value -= 1 # Ya puede pasar el coche al norte
            self.turn.value = 1 # Indicamos que es nuestro turno. Esto es por si es el turno 0 en el que no pasaba nadie
            self.num_coches_norte.value += 1 # Indicamos que hay un coche más hacia el norte en nuestro puente
        elif direction == SOUTH:
            self.sur_coches_esperando.value += 1 # sumamos uno a los coches esperando para el sur
            self.coches_sur.wait_for(self.pasa_coche_sur) # Esperamos  a que pueda pasar el coche al sur
            self.sur_coches_esperando.value -= 1 # Ya puede pasar el coche al sur
            self.turn.value = 2 # Indicamos que es nuestro turno. Esto es por si era el turno 0 
            self.num_coches_sur.value += 1 # Indicamos que hay un coche más hacia el sur en nuestro puente
        self.mutex.release()
                
    def leaves_car(self, direction: int) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        if direction == NORTH:
            self.num_coches_norte.value -= 1 # Indicamos que hay un coche menos hacia el norte en nuestro puente
            # Una vez ha cruzado el puente el primero, vamos a cambiar el turno y analizar la situación.
            if self.sur_coches_esperando.value != 0: 
                self.turn.value = 2
            elif self.peatones_esperando.value != 0:
                self.turn.value = 3
            else:
                self.turn.value = 0
            if self.num_coches_norte.value == 0: # Cuando ya no queden coches hacia el norte dentro de nuestro puente.
                self.coches_sur.notify_all() # hacemos un notify a los coches del sur 
                self.peatones.notify_all()  # hacemos un notify a los peatones
            
        elif direction == SOUTH:
            self.num_coches_sur.value -= 1 # Indicamos que hay un coche menos hacia el sur en nuestro puente
            # Una vez ha cruzado el puente el primero, vamos a cambiar el turno y analizar la situación.
            if self.peatones_esperando.value != 0:
                self.turn.value = 3
            elif self.norte_coches_esperando.value != 0:
                self.turn.value = 1
            else:
                self.turn.value = 0
            if self.num_coches_sur.value == 0: # Cuando ya no queden coches hacia el sur dentro de nuestro puente.
                self.coches_norte.notify_all() # hacemos un notify a los coches del norte
                self.peatones.notify_all() # hacemos un notify a los peatones
        self.mutex.release()
    
    def wants_enter_pedestrian(self) -> None:
        self.mutex.acquire()
        self.patata.value += 1 
        self.peatones_esperando.value += 1 # sumamos uno a los peatones esperando
        self.peatones.wait_for(self.pasa_peaton) # esperamos a que puedan pasar los peatones
        self.peatones_esperando.value -= 1 # ya puede pasar el peaton
        self.turn.value = 3 # Indicamos que es nuestro turno. Esto es por si era el turno 0
        self.num_peatones.value += 1 # Sumamos en uno el número de peatones en el puente
        self.mutex.release()
        
    def leaves_pedestrian(self) -> None:
        self.mutex.acquire()
        self.patata.value += 1
        self.num_peatones.value -= 1 # Indicamos que hay un peatón menos en nuestro puente
        # Una vez ha cruzado el puente el primero, vamos a cambiar el turno y analizar la situación.
        if self.norte_coches_esperando.value != 0:
            self.turn.value = 1
        elif self.sur_coches_esperando.value != 0:
            self.turn.value = 2
        else:
            self.turn.value = 0
        if self.num_peatones.value == 0: # Cuando ya no queden peatones dentro de nuestro puente.
            self.coches_norte.notify_all() # hacemos un notify a los coches del norte
            self.coches_sur.notify_all() # hacemos un notify a los peatones 
        self.mutex.release()
    """
        ¿Cómo funcionan los turnos?:
            Los turnos van rotando entre turn 1 --> turn 2 --> turn 3 --> turn 1, para que 
            no hay inanición en ningún momento. 
            Pero, nos debemos asegurar que cuando se cambia turno hay algún coche esperando en dicha dirección
            o un peaton en su defecto. Por ello distinguimos los distintos casos en leave_car y en leave_pedestrian.
            Además, puede darse la situación de que no haya nadie en el puente para pasar. Por ello, se introduce el 
            turn 0, que indica el paso libre para el que primero llegue o este esperando. El turno 0 también se ha utilizado 
            para indicar que no se cambia turno cuando en una dirección esten pasando y no haya nadie esperando
            en la otra dirección ni ningún peaton, o en su defecto, hay peatones pasando sin ningún coche esperando.
    
    """
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
