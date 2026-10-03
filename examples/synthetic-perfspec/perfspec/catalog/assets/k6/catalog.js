import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = {
  scenarios: { catalog: { executor: 'constant-vus', vus: 1, duration: '60s', gracefulStop: '10s' } },
  thresholds: { 'http_req_duration{name:catalog}': ['p(95)<=500'], checks: ['rate==1'] },
};
export default function () {
  const response = http.get(`${__ENV.BASE_URL}/catalog`, { tags: { name: 'catalog' } });
  check(response, { 'catalog returns 200': r => r.status === 200 });
  sleep(1);
}
