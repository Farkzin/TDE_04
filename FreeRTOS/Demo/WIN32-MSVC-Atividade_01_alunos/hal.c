#include "hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "basic_io.h"
#include <stdio.h>
#include <conio.h>

boolean pinTurnSignal_LEFT;
boolean pinTurnSignal_RIGHT;
tuCommand lastCommand;

static void showSignals(void) {
	char texto[80];
	sprintf(texto, "ESQUERDO: %s   |   DIREITO: %s\r\n",
		pinTurnSignal_LEFT  ? "LIGADO " : "apagado",
		pinTurnSignal_RIGHT ? "LIGADO " : "apagado");
	vPrintString(texto);
}

void task_Key(void *pParam){
	char tecla;

	for (;;) {
		if (_kbhit()) {
			tecla = _getch();

			if (tecla == 'l' || tecla == 'L') {
				lastCommand.TurnCommands = command_Left;
			}
			else if (tecla == 'r' || tecla == 'R') {
				lastCommand.TurnCommands = command_Right;
			}
			else if (tecla == ' ') {
				lastCommand.TurnCommands = command_None;
			}
			else if (tecla == 'a' || tecla == 'A') {
				lastCommand.Alert = !lastCommand.Alert;
			}
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

void InitHAL() {
	pinTurnSignal_LEFT = FALSE;
	pinTurnSignal_RIGHT = FALSE;
	lastCommand.TurnCommands = command_None;
	lastCommand.Alert = 0;

	vPrintString("Teclas: l = esquerda | r = direita | espaco = desliga | a = pisca-alerta\r\n");
	showSignals();

	xTaskCreate(task_Key, "Key", configMINIMAL_STACK_SIZE, NULL, 1, NULL);
}

tuCommand getTurnCommand() {
	return lastCommand;
}

void TurnSignalRight(boolean s) {
	if (pinTurnSignal_RIGHT != s) {
		pinTurnSignal_RIGHT = s;
		showSignals();
	}
}

void TurnSignalLeft(boolean s) {
	if (pinTurnSignal_LEFT != s) {
		pinTurnSignal_LEFT = s;
		showSignals();
	}
}

void ToggleTurnSignalRight() {
	pinTurnSignal_RIGHT = !pinTurnSignal_RIGHT;
	showSignals();
}

void ToggleTurnSignalLeft() {
	pinTurnSignal_LEFT = !pinTurnSignal_LEFT;
	showSignals();
}
