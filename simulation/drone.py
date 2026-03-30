class Drone:
    def __init__(self, drone_id, x, y, battery=100):
        self.id = drone_id
        self.x = x
        self.y = y
        self.battery = battery
        self.task = None

    def __repr__(self):
        return f"Drone {self.id} at ({self.x},{self.y}) battery={self.battery} task={self.task}"
