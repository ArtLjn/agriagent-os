## 1. 后端预报缓存

- [ ] 1.1 在 `backend/app/services/weather/` 下新建 `cache.py`，实现 `WeatherCache` 类：进程内 dict + TTL，`get(key)` / `set(key, value, ttl)` / `make_key(location, days, lat, lon)`
- [ ] 1.2 在 `strategy.py` 的 `fetch()` 中集成缓存：先查缓存，miss 时走 provider 并写入缓存，预报 TTL=600s
- [ ] 1.3 编写 `tests/test_weather_cache.py`：验证缓存命中/过期/多城市隔离

## 2. 后端预警独立缓存

- [ ] 2.1 在 `cache.py` 中增加预警缓存方法，TTL=1800s，key 为城市名
- [ ] 2.2 修改 `strategy.py` 的预警获取逻辑：先查预警缓存，miss 时 `asyncio.to_thread` 抓取并写入缓存
- [ ] 2.3 编写测试：验证预警缓存命中不触发网络请求

## 3. 前端 AsyncStorage 缓存

- [ ] 3.1 修改 `agentStore.ts`：`fetchWeather` 成功后将天气数据写入 AsyncStorage（key=`weather_cache_${cityName}`）
- [ ] 3.2 修改 `agentStore.ts`：初始化时从 AsyncStorage 读取缓存天气数据，有缓存则立即更新 state
- [ ] 3.3 确保后台刷新正常：缓存展示后发起网络请求，响应后静默替换 state

## 4. 集成验证

- [ ] 4.1 启动后端，连续请求同一城市天气，验证第二次无外部 HTTP 调用
- [ ] 4.2 等待 10 分钟后再次请求，验证缓存过期并重新获取
- [ ] 4.3 安装 App 到模拟器，验证打开后秒出缓存天气数据
