# JMeter 适配参考

仅在选用 JMeter 时读取。JMX 是原生资产，正式执行采用 CLI；记录版本、Java、线程组和所有插件版本。

## 负载与资产

- 标准 Thread Group 表达并发线程的 closed 模型；线程数不等于 RPS。ramp-up 只定义线程增长时间。
- open 到达率模型需要明确的原生线程组/插件或自定义方案及当前版本验证依据，不能把 throughput timer 自动宣称为严格开放调度。
- 根据明确 endpoint 与业务 oracle 生成 HTTP sampler、Header/Cookie Manager、提取器、断言、CSV 配置和事务计时。未知成功码不默认 200；业务字段断言失败计入功能失败。
- 稳定 sampler label 对应 step ID，transaction parent 区分业务旅程和请求。保存 request/transaction 两层样本，不重复计数。
- CSV 的共享粒度、recycle、EOF stop、header/变量配置明确一致；分布式节点各自数据分片，不能假定自动共享 CSV。
- secret 从受控环境读取（例如 Groovy `System.getenv`），或已确认安全的注入机制；不杜撰核心 `__env` 函数。避免明文 properties、命令行和日志泄露。
- 静态检查 XML/hash 与实际加载验证分开；正式压测避免 View Results Tree 等重型监听器，不保存业务响应正文。

## 执行与结果

交接命令示意，具体参数来自计划；仅 run 阶段在授权范围执行：

```sh
jmeter -n -t <plan.jmx> -l <new-run>/raw/results.jtl \
  -j <new-run>/raw/jmeter.log -e -o <new-run>/raw/html
```

HTML 目录需不存在或为空。创建目录时不要预创建该 HTML 目录。JVM heap、分布式机器、插件和脚本输入纳入有效配置。
JTL 保存 timeStamp、elapsed、label、success、responseCode、线程/数据字段中实际需要的非秘密指标；精确稳态判定保留可分窗原始数据。HTML summary 的全程统计不能替代计划的测量窗口。
从 measured request/transaction 样本判断业务/SLA；不要把 CLI exit 0 当成样本成功或 SLA 通过。elapsed 的计时范围及重定向等设置按当前工具版本说明，跨工具不直接等同。
优雅中止使用当前安装工具支持的 shutdown 机制，仅针对本次进程/节点；中断 JTL 保留但不宣称完整负载完成。

## 官方依据

- [Getting started / CLI](https://jmeter.apache.org/usermanual/get-started.html)
- [Best practices](https://jmeter.apache.org/usermanual/best-practices.html)
- [Components / CSV / assertions / thread groups](https://jmeter.apache.org/usermanual/component_reference.html)
- [Distributed testing](https://jmeter.apache.org/usermanual/remote-test.html)

这些建议不证明本地 JMeter 或插件可用；实际执行需采集就绪证据。
