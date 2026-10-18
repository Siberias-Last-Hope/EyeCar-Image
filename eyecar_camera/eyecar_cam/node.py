import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from cv_bridge import CvBridge


def init(args=None):
    if not rclpy.ok():
        rclpy.init(args=args)


class CameraNode(Node):

    def __init__(self, name='cv'):
        init()
        super().__init__(name)
        self.bridge = CvBridge()

    def subscribe(self, callback, throttled=False):
        topic = 'camera/image_raw_throttled' if throttled else 'camera/image_raw'
        return self.create_subscription(Image, topic, callback, qos_profile_sensor_data)

    def grab(self, timeout=5.0):
        frame = []
        sub = self.subscribe(frame.append)
        deadline = self.get_clock().now().nanoseconds + int(timeout * 1e9)
        while not frame and self.get_clock().now().nanoseconds < deadline and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
        self.destroy_subscription(sub)
        return self.bridge.imgmsg_to_cv2(frame[0], 'bgr8') if frame else None

    def debug_publisher(self, topic='~/debug'):
        """Publisher for annotated frames; view it at /<node>/debug in the browser."""
        pub = self.create_publisher(Image, topic, 1)

        def publish(img):
            pub.publish(self.bridge.cv2_to_imgmsg(img, 'bgr8'))
        return publish
