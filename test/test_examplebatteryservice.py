from datetime import datetime
import unittest
from dots_infrastructure.DataClasses import SimulatorConfiguration, TimeStepInformation
from esdl.esdl_handler import EnergySystemHandler
import helics as h
from dataclasses import dataclass

from dots_infrastructure import CalculationServiceHelperFunctions

from dots_infrastructure.test_infra.InfluxDBMock import InfluxDBMock

from ExampleBatteryService.example_battery_service import ExampleBatteryService


BROKER_TEST_PORT = 23404
START_DATE_TIME = datetime(2024, 1, 1, 0, 0, 0)
SIMULATION_DURATION_IN_SECONDS = 960
TEST_ID = "de40bae7-0ebe-4be8-9457-590a0657753e"

@dataclass
class MaxChargeAndDischargeTestCase:
    current_charge_joules: float
    expected_max_charge_watts: float
    expected_max_discharge_watts: float

@dataclass
class ChargeTestcase:
    current_charge_joules: float
    amount_to_charge: float

def simulator_environment_e_connection():
    return SimulatorConfiguration("Battery", [TEST_ID], "Mock-Battery", "127.0.0.1", BROKER_TEST_PORT, "test-id", SIMULATION_DURATION_IN_SECONDS, START_DATE_TIME, "test-host", "test-port", "test-username", "test-password", "test-database-name", h.HelicsLogLevel.DEBUG, ["PVInstallation", "EConnection"])

class Test(unittest.TestCase):

    def setUp(self):
        CalculationServiceHelperFunctions.get_simulator_configuration_from_environment = simulator_environment_e_connection
        esh = EnergySystemHandler()
        esh.load_file("test.esdl")
        self.energy_system = esh.get_energy_system()

    def test_when_max_charge_and_discharg_are_calculated_correct_values_come_out(self):
        max_discharge_testcases = [
            MaxChargeAndDischargeTestCase(
                current_charge_joules = 37566460.03281124,
                expected_max_charge_watts=0,
                expected_max_discharge_watts=-3875.1465918455965
            ),
            MaxChargeAndDischargeTestCase(
                current_charge_joules = 2000,
                expected_max_charge_watts=3875.1465918455965,
                expected_max_discharge_watts=-2.222222222222222222222222
            ),
            MaxChargeAndDischargeTestCase(
                current_charge_joules = 3500000,
                expected_max_charge_watts=3875.1465918455965,
                expected_max_discharge_watts=-3875.1465918455965
            ),
        ]

        for i in range(0, len(max_discharge_testcases)):
            with self.subTest(i=i, params = max_discharge_testcases[i]):
                battery_service = ExampleBatteryService()
                battery_service.init_calculation_service(self.energy_system)
                battery_service.current_charge[TEST_ID] = max_discharge_testcases[i].current_charge_joules
                output = battery_service.max_charge_and_discharge({}, START_DATE_TIME, TimeStepInformation(0, SIMULATION_DURATION_IN_SECONDS), TEST_ID, self.energy_system)
                self.assertAlmostEqual(output.max_charge_active_power, max_discharge_testcases[i].expected_max_charge_watts)
                self.assertAlmostEqual(output.max_discharge_active_power, max_discharge_testcases[i].expected_max_discharge_watts)

    def test_when_battery_gets_over_or_under_charged_value_error_is_raised(self):
        test_cases = [
            ChargeTestcase(
                current_charge_joules = 37566460.03281124,
                amount_to_charge = 3875.1465918455965
            ),
            ChargeTestcase(
                current_charge_joules = 0,
                amount_to_charge = -10
            ),
        ]
        for i in range(0, len(test_cases)):
            with self.subTest(i=i, params = test_cases[i]):
                battery_service = ExampleBatteryService()
                battery_service.init_calculation_service(self.energy_system)
                battery_service.current_charge[TEST_ID] = test_cases[i].current_charge_joules
                amount_to_charge = test_cases[i].amount_to_charge

                # Act / Assert
                with self.assertRaises(ValueError):
                    battery_service.charge_battery({"active_power_to_charge": amount_to_charge}, START_DATE_TIME, TimeStepInformation(0, SIMULATION_DURATION_IN_SECONDS), TEST_ID, self.energy_system)

    def test_when_battery_gets_charged_soc_is_written_to_influx(self):
        test_cases = [
            ChargeTestcase(
                current_charge_joules = 10000000,
                amount_to_charge = 3875.1465918455965
            ),
            ChargeTestcase(
                current_charge_joules = 10000000,
                amount_to_charge = -3875.1465918455965
            ),
        ]
        for i in range(0, len(test_cases)):
            battery_capacity = 37566460.03281124
            with self.subTest(i=i, params = test_cases[i]):
                battery_service = ExampleBatteryService()
                influx_mock = InfluxDBMock()
                battery_service.influx_connector = influx_mock
                battery_service.init_calculation_service(self.energy_system)
                battery_service.current_charge[TEST_ID] = test_cases[i].current_charge_joules

                # Act
                battery_service.charge_battery({"active_power_to_charge": test_cases[i].amount_to_charge}, START_DATE_TIME, TimeStepInformation(0, SIMULATION_DURATION_IN_SECONDS), TEST_ID, self.energy_system)

                # Assert
                joules_to_charge = test_cases[i].amount_to_charge * 900
                percentage = ((test_cases[i].current_charge_joules + joules_to_charge) / battery_capacity) * 100
                value_written = influx_mock.data_points[0]
                self.assertAlmostEqual(value_written.value, percentage)

if __name__ == '__main__':
    unittest.main()
