#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import PoseStamped, PointStamped
import numpy as np
from filterpy.kalman import KalmanFilter as KF

'''
[[]]  [ , ]
1x1-R 1x3-H 3x1-B/x 3x3-F
'''
class optionalEKF(KF):
	def __init__(self, 
			  	dim_x: int, 
				dim_z: int, 
				dim_u: int, 
				):
		super().__init__(dim_x=dim_x, dim_z=dim_z, dim_u=dim_u)
		if self.dim_x == 2:
			self.H = np.array([[1, 0]])
			self.R = np.array([[0.05]])
			self.Q = np.diag([0.01, 100])
	
	def load_x0(self,
			 	x0: np.array):
		self.x = x0
		
	def load_FB(self, dt):
		self.dt = dt
		if self.dim_x == 2:
			self.F = np.array([[1, dt],
				   			[0, 1]])
			self.B = np.array([[0], [dt]])
		
	def predict_update(self, pos, u=None):
		if u is not None:
			self.predict(u)
		else:
			self.predict()
		self.update(pos)

def get_kf_output(kf, pose, dt):
	kf.dt = dt
	if kf.x[1, 0] > 0:
		kf.F = np.array([[1, dt - kf.x[2, 0] * kf.x[1, 0] * dt ** 2, - 0.5 * kf.x[1, 0] ** 2 * dt ** 2],
						[0, 1 - 2 * kf.x[2, 0] * kf.x[1, 0] * dt, - kf.x[1, 0] ** 2 * dt],
						[0, 0, 1]])
	elif kf.x[1, 0] == 0:
		kf.F = np.array([[1, dt, 0],
						[0, 0, 0],
						[0, 0, 1]])
	else:
		kf.F = np.array([[1, dt + kf.x[2, 0] * kf.x[1, 0] * dt ** 2, 0.5 * kf.x[1, 0] ** 2 * dt ** 2],
						[0, 1 + 2 * kf.x[2, 0] * kf.x[1, 0] * dt, kf.x[1, 0] ** 2 * dt],
						[0, 0, 1]])
	kf.B = np.array([[0], [dt], [0]])
	kf.predict(u=-9.8)
	kf.update(pose)
	return kf.x.copy()

kf = KF(dim_x=3, dim_z=1, dim_u=1)
x0, v0, k0, dt = 1.3, 4.0, 0.06, 1 / 120
kf.x = np.array([[x0], [v0], [k0]])
kf.dt = dt
kf.F = np.array([[1, dt, 0],
				[0, 1 - 2 * k0 * v0 * dt, - v0 ** 2 * dt],
				[0, 0, 1]])
kf.H = np.array([[1, 0, 0]])
kf.R = np.array([[0.04]])
kf.Q = np.diag([0.01, 1000000, 1000])
kf.B = np.array([[0], [dt], [0]])

first_frame = True
time_last = 0
pub_kf = rospy.Publisher('kf', PointStamped, queue_size = 1)

z_last = 0
pub_nv = rospy.Publisher('nv', PointStamped, queue_size = 1)

kf_vel = optionalEKF(dim_x=2, dim_z=1, dim_u=0)
pub_kf_vel = rospy.Publisher('kf_vel', PointStamped, queue_size = 1)

def callback(msg):
	global first_frame, time_last, kf, pose_last, z_last, kf_vel
	if first_frame == True:
		first_frame = False
		time_last = msg.header.stamp.to_sec()
		pose_last = msg.pose.position
		kf_vel.load_x0(x0=np.array([[pose_last.z],[0]]))
		return
	rospy.loginfo(f"class kf {kf_vel.dim_x}, {kf_vel.dim_z}, {kf_vel.dim_u}, {kf_vel.x}")
	
	time_now = msg.header.stamp.to_sec()
	dt = time_now - time_last
	
	z = msg.pose.position.z
	kf_output = get_kf_output(kf, z, dt)
	# rospy.loginfo(f"data: {kf_output.shape}")
 
	kf_vel.load_FB(dt)
	kf_vel.predict_update(z)
	
	kf_pub = PointStamped()
	kf_pub.header.stamp = rospy.Time.from_sec(time_now)
	kf_pub.point.x = kf_output[0, 0] # h
	kf_pub.point.y = kf_output[1, 0] # hdot
	kf_pub.point.z = kf_output[2, 0] # drag coefficient
	pub_kf.publish(kf_pub)

	nv_pub = PointStamped()
	nv_pub.header.stamp = kf_pub.header.stamp
	nv_pub.point.z = (z - z_last) / dt
	pub_nv.publish(nv_pub)

	kf_vel_pub = PointStamped()
	kf_vel_pub.header.stamp = kf_pub.header.stamp
	kf_vel_pub.point.y = kf_vel.x[1, 0]
	kf_vel_pub.point.z = kf_vel.x[0, 0]
	pub_kf_vel.publish(kf_vel_pub)
	
	time_last = time_now
	z_last = z



def main():
	rospy.init_node("kf", anonymous=True)
	rospy.loginfo("kf node init")

	pose_name = "/natnet_ros/ball/pose"
	rospy.Subscriber(pose_name, PoseStamped, callback)
	rospy.loginfo(f"kf node is subscribing {pose_name}")

	
	rospy.spin()


if __name__ == '__main__':
	try:
		main()
	except rospy.ROSInterruptException:
		print("Failed to start kf!")
		pass
