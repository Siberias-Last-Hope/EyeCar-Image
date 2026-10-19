import atexit
import threading
from time import monotonic, sleep

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

PUBLISH_RATE = 20.0


def _clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, float(value)))


class Car:

    def __init__(self, name='eyecar_car'):
        self._owns_rclpy = not rclpy.ok()
        if self._owns_rclpy:
            rclpy.init()
        self._node = Node(name)
        self._lock = threading.Lock()
        self._motor = 0.0
        self._steer = 0.0
        self._armed = False

        latched = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._cmd_pub = self._node.create_publisher(Twist, 'cmd_vel', 10)
        self._arm_pub = self._node.create_publisher(Bool, 'base/arm', latched)
        self._node.create_subscription(Bool, 'base/armed', self._on_armed, latched)
        self._node.create_timer(1.0 / PUBLISH_RATE, self._repeat)

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._thread.start()
        atexit.register(self.close)

    # ---- state

    @property
    def armed(self):
        return self._armed

    @armed.setter
    def armed(self, value):
        if value:
            self.arm()
        else:
            self.disarm()

    @property
    def speed(self):
        return self._motor

    @property
    def steering(self):
        return self._steer

    # ---- arm

    def arm(self, timeout=2.0):
        self._arm_pub.publish(Bool(data=True))
        deadline = monotonic() + timeout
        while not self._armed:
            if monotonic() > deadline:
                raise RuntimeError(
                    'the car did not confirm arm: is base_node running and the Arduino connected?')
            sleep(0.02)

    def disarm(self):

        self._arm_pub.publish(Bool(data=False))
        self.stop()

    # ---- steering

    def steer(self, value):
        with self._lock:
            self._steer = _clamp(value)
        self._send()

    def left(self, amount=1.0):
        self.steer(abs(amount))

    def right(self, amount=1.0):
        self.steer(-abs(amount))

    def center(self):
        self.steer(0.0)

    # ---- wheels

    def drive(self, speed):
        with self._lock:
            self._motor = _clamp(speed)
        self._send()

    def stop(self):
        self.drive(0.0)

    def navigate_time(self, time, speed, arm=None, steer=None):
        if arm is not None:
            self.armed = arm
        if steer is not None:
            self.steer(steer)
        if not self._armed:
            self._node.get_logger().info('car is disarmed: the wheels are blocked')
        self.drive(speed)
        try:
            deadline = monotonic() + time
            while True:
                left = deadline - monotonic()
                if left <= 0:
                    break
                sleep(min(0.02, left))
        finally:
            self.stop()

    def close(self):
        if not self._thread.is_alive():
            return
        self.stop()
        self._executor.shutdown()
        self._node.destroy_node()
        if self._owns_rclpy and rclpy.ok():
            rclpy.shutdown()


    def _on_armed(self, msg):
        self._armed = msg.data

    def _send(self):
        with self._lock:
            msg = Twist()
            msg.linear.x = self._motor
            msg.angular.z = self._steer
        self._cmd_pub.publish(msg)

    def _repeat(self):
        if self._motor != 0.0:
            self._send()
