import airsim


class AirSimDrone:
    def __init__(self, drone_name="Drone1"):
        # Creates a client object to communicate with the AirSim simulator:
        self.client = airsim.MultirotorClient()
        # checks that the connection to the simulator is working (it will print status info):
        self.client.confirmConnection()
        
        self.drone_name = drone_name

    def enable(self):
        # Gives the script control over the drone:
        self.client.enableApiControl(True, self.drone_name)
        # Arm the drone (allow it to take off). “Arming” prepares the drone’s motors so it can take off:
        self.client.armDisarm(True, self.drone_name)

    def takeoff(self):
        # Commands the drone to take off and (join) waits until it has completed the takeoff process:
        self.client.takeoffAsync(vehicle_name=self.drone_name).join()

    def land(self):
        # Commands the drone to land and waits until it has completed the landing process:
        self.client.landAsync(vehicle_name=self.drone_name).join()

    def get_state(self):
        # Retrieves the current state of the drone, including its position, velocity, and orientation:
        return self.client.getMultirotorState(vehicle_name=self.drone_name)

    def get_image(self):
        response = self.client.simGetImages([
            airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)
        ], vehicle_name=self.drone_name)

        return response[0]

    def move_drone(self, x, y, z, speed=5):
        self.client.moveToPositionAsync(x, y, z, speed)