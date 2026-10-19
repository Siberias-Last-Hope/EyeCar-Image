import asyncio
import json
import os
import threading

import rclpy
from aiohttp import WSMsgType, web
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

STATE_PERIOD = 0.2


def clamp(value):
    return max(-1.0, min(1.0, float(value)))


class WebTeleop(Node):
    """Browser control: serves /teleop/ and turns its WebSocket frames into ROS messages.

    The page sends {"t": "drive", "m": speed, "s": steering} while its control switch is on
    and {"t": "arm", "v": bool}. Nothing is sent otherwise, so scripts can drive the car
    while the page is open. If the page goes quiet, base_node stops the wheels.
    """

    def __init__(self):
        super().__init__('web_teleop')
        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 80)
        self.declare_parameter('web_dir', os.path.join(
            get_package_share_directory('eyecar_teleop'), 'web'))

        latched = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._cmd_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self._arm_pub = self.create_publisher(Bool, 'base/arm', latched)
        self.create_subscription(Bool, 'base/armed', self._on_armed, latched)
        self.armed = False

    def _on_armed(self, msg):
        self.armed = msg.data

    def drive(self, motor, steer):
        msg = Twist()
        msg.linear.x = clamp(motor)
        msg.angular.z = clamp(steer)
        self._cmd_pub.publish(msg)

    def set_arm(self, value):
        self._arm_pub.publish(Bool(data=bool(value)))

    def make_app(self):
        web_dir = self.get_parameter('web_dir').value
        index = os.path.join(web_dir, 'index.html')

        async def page(_request):
            return web.FileResponse(index, headers={'Cache-Control': 'no-cache'})

        async def to_page(_request):
            raise web.HTTPFound('/teleop/')

        async def socket(request):
            ws = web.WebSocketResponse(heartbeat=5.0)
            await ws.prepare(request)
            sender = asyncio.ensure_future(self._push_state(ws))
            driven = False
            try:
                async for raw in ws:
                    if raw.type == WSMsgType.TEXT:
                        driven = self._on_frame(raw.data) or driven
            finally:
                sender.cancel()
                if driven:
                    self.drive(0.0, 0.0)
            return ws

        app = web.Application()
        app.add_routes([
            web.get('/', to_page),
            web.get('/teleop', to_page),
            web.get('/teleop/', page),
            web.get('/teleop/ws', socket),
        ])
        return app

    def _on_frame(self, text):
        try:
            frame = json.loads(text)
            if frame['t'] == 'drive':
                self.drive(frame['m'], frame['s'])
                return True
            if frame['t'] == 'arm':
                self.set_arm(frame['v'])
        except (ValueError, KeyError, TypeError):
            self.get_logger().warning('bad frame from the page: %.80s' % text)
        return False

    async def _push_state(self, ws):
        while not ws.closed:
            await ws.send_json({'armed': self.armed})
            await asyncio.sleep(STATE_PERIOD)


def main():
    rclpy.init()
    node = WebTeleop()
    spinner = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spinner.start()
    try:
        web.run_app(
            node.make_app(),
            host=node.get_parameter('host').value,
            port=node.get_parameter('port').value,
            print=lambda text: node.get_logger().info(text))
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
