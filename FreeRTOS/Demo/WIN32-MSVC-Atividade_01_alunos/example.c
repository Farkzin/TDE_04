
#include "FreeRTOS.h"
#include "task.h"

#include "basic_io.h"
#include "hal.h"
#include "sm.h"

#define TEMPO_INVERTER_MS	333

StateMachine smBlink;

STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

STATE(state_BLINK_NONE) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
}

STATE(state_BLINK_LEFT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

STATE(state_BLINK_RIGHT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

STATE(state_BLINK_ALERT) {
	tuCommand cmd = getTurnCommand();

	if (!cmd.Alert) {
		if (cmd.TurnCommands == command_Left)       NEXT_STATE(state_BLINK_LEFT);
		else if (cmd.TurnCommands == command_Right) NEXT_STATE(state_BLINK_RIGHT);
		else                                        NEXT_STATE(state_BLINK_NONE);
	}
}

static boolean faseAcesa(void) {
	return (boolean)((xTaskGetTickCount() / (TEMPO_INVERTER_MS / portTICK_PERIOD_MS)) % 2);
}

void task_BlinkLeft(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_LEFT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalLeft(faseAcesa());
		}
		else {
			TurnSignalLeft(FALSE);
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

void task_BlinkRight(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_RIGHT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalRight(faseAcesa());
		}
		else {
			TurnSignalRight(FALSE);
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

void task_StateMachine(void *pParam) {
	for (;;) {
		EXEC(smBlink);
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

int main_(void)
{
	InitHAL();
	INIT(smBlink, state_BLINK_NONE);

	xTaskCreate(task_StateMachine, "StateMachine", configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(task_BlinkLeft,    "BlinkLeft",    configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(task_BlinkRight,   "BlinkRight",   configMINIMAL_STACK_SIZE, NULL, 1, NULL);

	vTaskStartScheduler();
	return 0;
}
