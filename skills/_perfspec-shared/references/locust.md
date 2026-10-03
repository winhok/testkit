# Locust 适配参考

Locust 原生 Python 场景适合复杂业务旅程；使用当前宿主已安装版本，不隐式 pip install。

## 负载与脚本

- HttpUser/FastHttpUser 的用户循环是 closed 模型；users 是用户数，spawn-rate 是增长速度，均不是固定全局请求速率。
- `constant_throughput` 限制每用户 task 执行频率；task 可含多个请求，响应耗时增加时并不保证全局开放到达率。`LoadTestShape` 控制用户曲线，不能单凭它宣称严格 open。
- 精确 open 模型作为 conditional/unsupported 处理，除非已验证自定义调度；否则建议选择能表达该语义的工具，保留用户最终选择。
- 一个完整业务旅程可作为 task，显式关联 login/token/entity。任务权重不自动证明 HTTP 配比；按实际场景频率验证。
- 每请求使用稳定 name，`catch_response` 依据已确认业务字段/状态判成功。请求失败与整个旅程未完成分开采集；业务旅程计时需要真实 instrumentation，不用请求均值替代。
- 数据分片按 worker/user 分配，别让每个 worker 从相同 CSV 首行开始。on_start/on_stop 清理受本次实体范围约束；异常中断后另核对清理。
- import/初始化可以有副作用，py_compile 仅语法检查。启动 Locust 和导入待测脚本属于 run 的就绪验证。

## 执行与结果

```sh
locust -f <locustfile.py> --headless --host <authorized-base-url> \
  --users <users> --spawn-rate <users-per-second> --run-time <duration> \
  --stop-timeout <seconds> --csv <new-run>/raw/locust --csv-full-history
```

run-time 从测试启动计时，包含 ramp。分布式运行确认 master/worker 数量与版本，master 可用 `--expect-workers` 等待所需 worker。是否多进程按平台支持和版本文档确定。
默认退出码可以反映失败请求；SLA 门槛需明确 quitting hook 或执行后评估。退出 0 不自动证明业务完成率或延迟门槛。
CSV 统计提供汇总/历史，未必有计划所需的精确分窗样本和业务完成统计；需要时提前配置 request events 收集器，控制开销并脱敏。不把累计 P95 当稳态 P95，不对 workers P95 求平均。
关注 generator CPU/网络，确认客户端 gevent 兼容性；FastHttpUser 会改变客户端，应记录并核对与基线一致性。

## 官方依据

- [Headless / time / CI exit status](https://docs.locust.io/en/stable/running-without-web-ui.html)
- [API / wait time / catch_response](https://docs.locust.io/en/stable/api.html)
- [Load shapes](https://docs.locust.io/en/stable/custom-load-shape.html)
- [Throughput diagnosis](https://docs.locust.io/en/stable/increasing-request-rate.html)
- [CSV statistics](https://docs.locust.io/en/stable/retrieving-stats.html)
