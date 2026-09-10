# 缺陷证据审阅与采样

使用环境实际可用的媒体工具，命令参数以当前工具帮助为准。输出到新的临时目录，保留源视频。先查看 metadata，再选范围；禁止下载或安装新工具后绕过平台执行权限。

粗采样用于定位片段，短暂闪烁需局部连续播放或更密集采样。采样间隔大于异常持续时间时，未发现不等于不存在。变量帧率、剪辑、倍速或掉帧可能使 frame number 与时间不线性对应，以媒体时间戳为准。

sample_video.py 的 sample.json 提供源视频 SHA-256 和逐帧采样时间映射。当前映射按请求的采样间隔估算，precision=approximate，不是源视频实际 PTS；提单时明确写“约”，精确定位仍须回看原视频。源文件在采样期间变化会拒绝形成有效 manifest，保留的部分输出不能当作已审阅证据。

报告包括 source identifier、duration、reviewed intervals、sampling strategy、timeline、observed symptoms、hypotheses、unobserved facts。每条结论引用实际看过的帧/区间。画面冻结可能来自录制停顿、网络等待或应用卡死，单个截图无法区分。

复现线索记录入口、可见账号角色、动作顺序、状态和异常时点；不从画面猜测密码、用户身份或未展示操作。分享帧前脱敏个人信息，保持原件与脱敏副本关联。
