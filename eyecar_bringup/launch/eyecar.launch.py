from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('camera', default_value='true'),
        DeclareLaunchArgument('video_device', default_value='/dev/video0'),
        Node(
            package='v4l2_camera',
            executable='v4l2_camera_node',
            name='camera',
            parameters=[{'video_device': LaunchConfiguration('video_device')}],
            condition=IfCondition(LaunchConfiguration('camera')),
            output='screen',
        ),
        Node(
            package='eyecar_camera',
            executable='camera_node',
            name='camera_throttle',
            parameters=[{'rate': 5.0}],
            condition=IfCondition(LaunchConfiguration('camera')),
            output='screen',
        ),
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='web_video_server',
            parameters=[{'port': 8080}],
            output='screen',
        ),
        Node(
            package='foxglove_bridge',
            executable='foxglove_bridge',
            name='foxglove_bridge',
            parameters=[{'port': 8765}],
            output='screen',
        ),
    ])
