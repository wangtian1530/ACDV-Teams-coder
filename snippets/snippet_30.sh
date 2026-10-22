# Version mới
curl http://localhost:8765/api/status | python3 -m json.tool

# Boot info
curl http://localhost:8765/api/boot

# Storage usage của demo module
curl -X POST http://localhost:8765/api/modules/storage/usage \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}'