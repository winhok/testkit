# Allure CLI 安装指引

本项目的 Allure 报告依赖 [Allure Commandline](https://docs.qameta.io/allure/) 生成与查看。若未安装，按以下方式之一安装。

## macOS（推荐）

```bash
brew install allure
```

安装后执行 `allure --version` 验证。

## Windows

- 使用 Scoop：`scoop install allure`
- 或从 [GitHub Releases](https://github.com/allure-framework/allure2/releases) 下载 zip，解压后将 `bin` 加入 PATH。

## Linux

- 使用 SDKMAN：`sdk install allure`
- 或从 [GitHub Releases](https://github.com/allure-framework/allure2/releases) 下载对应包并配置 PATH。

## 官方文档

详细安装与版本说明：https://docs.qameta.io/allure/

安装完成后，在项目根目录执行：

```bash
allure serve allure-results
```

即可在浏览器中查看报告（需先通过 apitestspec-scenario-runner 等跑完测试并生成 `allure-results`）。
