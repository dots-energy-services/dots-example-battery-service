from datetime import datetime
import helics as h
from dots_infrastructure.DataClasses import TimeStepInformation, EsdlId, HelicsCalculationInformation
from dots_infrastructure.HelicsFederateHelpers import HelicsSimulationExecutor
from dots_infrastructure.Logger import LOGGER
from dots_infrastructure.CalculationServiceHelperFunctions import get_single_param_with_name
from esdl import EnergySystem
from ExampleBatteryService.example_battery_service_base import ExampleBatteryServiceBase
from ExampleBatteryService.example_battery_service_dataclasses import MaxChargeAndDischargeOutput, SendSocOutput

class ExampleBatteryService(ExampleBatteryServiceBase): 

    def init_calculation_service(self, energy_system: EnergySystem):
        super().init_calculation_service(energy_system)
        self.max_capacity : dict[EsdlId, float] = {}
        self.charge_efficiency : dict[EsdlId, float] = {}
        self.max_charge_rate : dict[EsdlId, float] = {}
        self.discharge_efficiency : dict[EsdlId, float] = {}
        self.max_discharge_rate : dict[EsdlId, float] = {}
        self.current_charge : dict[EsdlId, float] = {}
        self.max_charge_and_discharge_period_seconds = 900
        for id, esdl_object in self.esdl_obj_mapping.items():
            self.max_capacity[id] = esdl_object.capacity
            self.current_charge[id] = esdl_object.fillLevel * esdl_object.capacity
            self.charge_efficiency[id] = esdl_object.chargeEfficiency
            self.discharge_efficiency[id] = esdl_object.dischargeEfficiency
            self.max_charge_rate[id] = esdl_object.maxChargeRate
            self.max_discharge_rate[id] = esdl_object.maxDischargeRate


    def max_charge_and_discharge(self, param_dict : dict, simulation_time : datetime, time_step_number : TimeStepInformation, esdl_id : EsdlId, energy_system : EnergySystem):
        max_amount_to_charge_joules = self.max_charge_and_discharge_period_seconds * self.charge_efficiency[esdl_id] * self.max_charge_rate[esdl_id]
        max_amount_to_discharge_joules = self.max_charge_and_discharge_period_seconds * self.max_discharge_rate[esdl_id] / self.discharge_efficiency[esdl_id]
        if self.current_charge[esdl_id] + max_amount_to_charge_joules > self.max_capacity[esdl_id]:
            max_amount_to_charge_joules = abs(self.max_capacity[esdl_id] - self.current_charge[esdl_id])
        if self.current_charge[esdl_id] - max_amount_to_discharge_joules < 0:
            max_amount_to_discharge_joules = -self.current_charge[esdl_id]

        max_amount_to_charge_watts = max_amount_to_charge_joules / (self.max_charge_and_discharge_period_seconds * self.charge_efficiency[esdl_id])
        max_amount_to_discharge_watts = max_amount_to_discharge_joules * self.discharge_efficiency[esdl_id] / self.max_charge_and_discharge_period_seconds

        if max_amount_to_discharge_watts > 0:
            max_amount_to_discharge_watts = -max_amount_to_discharge_watts

        return MaxChargeAndDischargeOutput(max_amount_to_charge_watts, max_amount_to_discharge_watts)


    def charge_battery(self, param_dict : dict, simulation_time : datetime, time_step_number : TimeStepInformation, esdl_id : EsdlId, energy_system : EnergySystem):
        amount_to_charge  = get_single_param_with_name(param_dict, "active_power_to_charge")
        # amount_to_charge_joules = self.max_charge_and_discharge_period_seconds * self.charge_efficiency[esdl_id] * amount_to_charge
        # Correct application of discharge efficiency:
        if amount_to_charge >= 0: # charging: only eta_ch of the terminal energy ends up in storage
            amount_to_charge_joules = self.max_charge_and_discharge_period_seconds * self.charge_efficiency[esdl_id] * amount_to_charge
        else: # discharging: storage loses terminal energy / eta_dis
            amount_to_charge_joules = self.max_charge_and_discharge_period_seconds * amount_to_charge / self.discharge_efficiency[esdl_id]
        if self.current_charge[esdl_id] + amount_to_charge_joules > self.max_capacity[esdl_id] + 1 or self.current_charge[esdl_id] + amount_to_charge_joules < -1:
            raise ValueError(f"Battery {esdl_id} cannot be charged with {amount_to_charge} W at time {simulation_time}. Current charge: {self.current_charge[esdl_id]} J, Max capacity: {self.max_capacity[esdl_id]} J")
        self.current_charge[esdl_id] += amount_to_charge_joules 
        state_of_charge = (self.current_charge[esdl_id] / self.max_capacity[esdl_id]) * 100
        LOGGER.debug(f"Battery {esdl_id} charged with {amount_to_charge} W at time {simulation_time}. New state of charge: {state_of_charge} %")
        self.influx_connector.set_time_step_data_point(esdl_id, "StateOfCharge", simulation_time, state_of_charge)


    def send_soc(self, param_dict : dict, simulation_time : datetime, time_step_number : TimeStepInformation, esdl_id : EsdlId, energy_system : EnergySystem):
        state_of_charge = self.current_charge[esdl_id]
        return SendSocOutput(state_of_charge)

if __name__ == "__main__":

    helics_simulation_executor = ExampleBatteryService()
    helics_simulation_executor.start_simulation()
    helics_simulation_executor.stop_simulation()
