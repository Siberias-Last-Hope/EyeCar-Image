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
            package='foxglove_bridge',
            executable='foxglove_bridge',
            name='foxglove_bridge',
            parameters=[{'port': 8765}],
            output='screen',
        ),
    ])
