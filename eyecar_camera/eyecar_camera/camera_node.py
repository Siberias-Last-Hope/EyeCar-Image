import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


class CameraThrottle(Node):

    def __init__(self):
        super().__init__('camera_throttle')
        self.declare_parameter('input_topic', 'camera/image_raw')
        self.declare_parameter('output_topic', 'camera/image_raw_throttled')
        self.declare_parameter('rate', 5.0)

        self._period = 1.0 / float(self.get_parameter('rate').value)
        self._last = None
        self._pub = self.create_publisher(
            Image, self.get_parameter('output_topic').value, qos_profile_sensor_data)
        self.create_subscription(
            Image, self.get_parameter('input_topic').value, self._on_image,
            qos_profile_sensor_data)

    def _on_image(self, msg):
        now = self.get_clock().now()
        if self._last is None or (now - self._last).nanoseconds * 1e-9 >= self._period:
            self._last = now
            self._pub.publish(msg)


def main():
    rclpy.init()
    node = CameraThrottle()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
