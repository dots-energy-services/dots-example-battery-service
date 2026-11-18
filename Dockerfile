FROM python:3.14

RUN mkdir /app/
WORKDIR /app

COPY src/ExampleBatteryService ./src/ExampleBatteryService
COPY pyproject.toml ./
COPY README.md ./

RUN pip install ./
ENTRYPOINT ["python3", "src/ExampleBatteryService/example_battery_service.py"]
