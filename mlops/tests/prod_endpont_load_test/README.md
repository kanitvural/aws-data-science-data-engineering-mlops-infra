# SageMaker Production Endpoint Load Test

This script simulates a load test on the SageMaker **Production Endpoint**, as if there were **5000 concurrent users** sending requests.  

The purpose of this test is to:
- Verify if **Auto Scaling** is working properly.
- Monitor **endpoint metrics** such as request counts, latency, and instance scaling.

---

## How to Monitor the Test

### 1. Check Endpoint Scaling in SageMaker
- Go to the **SageMaker Console**.
- Navigate to the **Production Endpoint** (e.g., `mlops-prod-endpoint`).
- In the **Settings** tab, observe the **Instance Count**.
- If Auto Scaling is working, the instance count should increase when the load test is running.

---

### 2. Monitor Metrics in CloudWatch

1. Go to **CloudWatch Console** → **All Metrics**.
2. Search for **`Invocations`**.
3. Navigate to:


4. Select the following metrics for your production endpoint (e.g., `mlops-prod-endpoint`):
- **Invocations**
- **InvocationsPerInstance**
- **ModelLatency**

---

### 3. Configure Metrics View

1. Go to **Graphed Metrics**.
2. For each metric, configure the **statistic type**:
- `Invocations` → **Sum**
- `InvocationsPerInstance` → **Sum**
- `ModelLatency` → **Average**
3. Set the **time period** (e.g., `2h`) in the **Custom range** option.
4. For `ModelLatency`, click the **arrow next to "Y Axis"** to move it to a separate Y-axis.  
This makes the average latency easier to analyze.

---

## Expected Behavior

- While the load test is running:
- The **number of invocations** will increase.
- **Auto Scaling** should launch additional instances when utilization is high.
- For example, during one test run, the instance count increased to **4** after hitting capacity.

- You can visually confirm:
- **Scaling events** in SageMaker.
- **Request throughput and latency trends** in CloudWatch.

---

## Notes
- High `ModelLatency` values may indicate that the endpoint requires more instances or larger instance types.
- Keep an eye on **errors** during the test; scaling may take a few minutes to stabilize.

# Automatic Trigger Scale Up

```
aws cloudwatch set-alarm-state --alarm-name "SMProdAutoScalingStage-SMProdAutoScalingStage-EndpointScalingTargetCPUScalingUpperAlarm7B8A87BA-1UCEzken3sco" --state-reason "testing recovery action" --state-value ALARM --region eu-central-1 
```
