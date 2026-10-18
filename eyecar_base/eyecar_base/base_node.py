import threading
import time

import rclpy
import serial
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

CMD_MAX = 1000


def clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


class BaseNode(Node):
    """Bridge between ROS topics and the Arduino base controller.

    cmd_vel   (geometry_msgs/Twist)  linear.x = motor, angular.z = steering, both -1..1
    base/arm  (std_msgs/Bool)        wheels allowed to turn; steering works either way
    base/armed (std_msgs/Bool)       arm state confirmed by the Arduino
    """

    def __init__(self):
        super().__init__('base')
        self.declare_parameter('port', '/dev/eyecar_arduino')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('rate', 20.0)
        self.declare_parameter('cmd_timeout', 0.5)
        self.declare_parameter('max_speed', 1.0)
        self.declare_parameter('steering_trim', 0.0)
        self.declare_parameter('steering_invert', False)

        self._lock = threading.Lock()
        self._port = None
        self._motor = 0.0
        self._steer = 0.0
        self._arm = False
        self._last_cmd = 0.0
        self._armed = None

        latched = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._armed_pub = self.create_publisher(Bool, 'base/armed', latched)
        self.create_subscription(Twist, 'cmd_vel', self._on_cmd, 10)
        self.create_subscription(Bool, 'base/arm', self._on_arm, latched)
        self.create_timer(1.0 / self.get_parameter('rate').value, self._tick)

        self._publish_armed(False)
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # ---- ROS side

    def _on_cmd(self, msg):
        with self._lock:
            self._motor = clamp(msg.linear.x)
            self._steer = clamp(msg.angular.z)
            self._last_cmd = time.monotonic()

    def _on_arm(self, msg):
        with self._lock:
            self._arm = msg.data
        self.get_logger().info('arm requested: %s' % msg.data)

    def _tick(self):
        """Send the wanted state to the Arduino; it repeats until the board's watchdog."""
        with self._lock:
            fresh = time.monotonic() - self._last_cmd < self.get_parameter('cmd_timeout').value
            motor = self._motor if fresh else 0.0
            motor *= clamp(self.get_parameter('max_speed').value, 0.0, 1.0)
            steer = self._steer
            arm = self._arm
        if self.get_parameter('steering_invert').value:
            steer = -steer
        steer = clamp(steer + self.get_parameter('steering_trim').value)
        frame = 'D,%d,%d,%d\n' % (round(motor * CMD_MAX), round(steer * CMD_MAX), int(arm))
        self._write(frame)

    def _publish_armed(self, armed):
        if armed != self._armed:
            self._armed = armed
            self._armed_pub.publish(Bool(data=armed))

    # ---- serial side

    def _write(self, text):
        port = self._port
        if port is None:
            return
        try:
            port.write(text.encode('ascii'))
        except (serial.SerialException, OSError) as err:
            self.get_logger().warning('serial write failed: %s' % err)
            self._close()

    def _close(self):
        port, self._port = self._port, None
        if port is not None:
            try:
                port.close()
            except (serial.SerialException, OSError):
                pass
        with self._lock:
            self._arm = False
            self._motor = 0.0
        self._publish_armed(False)

    def _open(self):
        name = self.get_parameter('port').value
        try:
            port = serial.Serial(name, self.get_parameter('baud').value, timeout=0.2)
        except (serial.SerialException, OSError) as err:
            self.get_logger().warning(
                'cannot open %s: %s' % (name, err), throttle_duration_sec=10.0)
            return False
        self.get_logger().info('opened %s' % name)
        with self._lock:
            self._arm = False
            self._motor = 0.0
        self._port = port
        return True

    def _read_loop(self):
        while self._running:
            if self._port is None and not self._open():
                time.sleep(1.0)
                continue
            try:
                raw = self._port.readline()
            except (serial.SerialException, OSError, AttributeError) as err:
                self.get_logger().warning('serial read failed: %s' % err)
                self._close()
                time.sleep(1.0)
                continue
            if raw:
                self._on_line(raw.decode('ascii', errors='replace').strip())

    def _on_line(self, line):
        fields = line.split(',')
        if fields[0] == 'S' and len(fields) == 5:
            self._publish_armed(fields[1] == '1')
            if fields[4] == '1':
                self.get_logger().warning(
                    'Arduino lost the link, motor stopped', throttle_duration_sec=5.0)
        elif fields[0] == 'R':
            self.get_logger().info('Arduino ready: %s' % line)
        elif fields[0] == 'E':
            self.get_logger().warning('Arduino rejected a line: %s' % line)

    def destroy_node(self):
        self._running = False
        self._write('D,0,0,0\n')
        self._close()
        super().destroy_node()


def main():
    rclpy.init()
    node = BaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
