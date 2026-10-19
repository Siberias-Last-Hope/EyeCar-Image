import select
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

HELP = """EyeCar keyboard teleop
  w / s   faster forward / reverse      space  stop the wheels
  a / d   steer left / right            x      centre the steering
  e       arm / disarm the wheels       q      quit
"""
STEP = 0.1
RATE = 20.0


def clamp(value):
    return max(-1.0, min(1.0, value))


class KeyboardTeleop(Node):

    def __init__(self):
        super().__init__('keyboard_teleop')
        latched = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._cmd_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self._arm_pub = self.create_publisher(Bool, 'base/arm', latched)
        self.create_subscription(Bool, 'base/armed', self._on_armed, latched)
        self._armed = False
        self._motor = 0.0
        self._steer = 0.0

    def _on_armed(self, msg):
        self._armed = msg.data

    def _key(self, key):
        """Apply one key; return False to quit."""
        if key == 'w':
            self._motor = clamp(self._motor + STEP)
        elif key == 's':
            self._motor = clamp(self._motor - STEP)
        elif key == ' ':
            self._motor = 0.0
        elif key == 'a':
            self._steer = clamp(self._steer + STEP)
        elif key == 'd':
            self._steer = clamp(self._steer - STEP)
        elif key == 'x':
            self._steer = 0.0
        elif key == 'e':
            self._arm_pub.publish(Bool(data=not self._armed))
        elif key == 'q':
            return False
        return True

    def run(self):
        print(HELP)
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0)
            if select.select([sys.stdin], [], [], 1.0 / RATE)[0]:
                if not self._key(sys.stdin.read(1)):
                    break
            msg = Twist()
            msg.linear.x = self._motor
            msg.angular.z = self._steer
            self._cmd_pub.publish(msg)
            print('\rspeed %+.1f  steering %+.1f  %s   '
                  % (self._motor, self._steer, 'ARMED' if self._armed else 'disarmed'),
                  end='', flush=True)
        self._cmd_pub.publish(Twist())
        print()


def main():
    rclpy.init()
    node = KeyboardTeleop()
    settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
