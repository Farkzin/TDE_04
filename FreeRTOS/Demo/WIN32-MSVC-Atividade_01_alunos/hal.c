/*
Camada de Abstracao do Hardware (HAL) para execucao no Visual Studio
*/

#include "hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "basic_io.h"
#include <stdio.h>
#include <conio.h>

// Variaveis da Camada de Abstracao do Hardware (HAL)
boolean pinTurnSignal_LEFT;		// Representa o estado do pino de saida do microcontrolador ligado ao sinalizador ESQUERDO
boolean pinTurnSignal_RIGHT;	// Representa o estado do pino de saida do microcontrolador ligado ao sinalizador DIREITO
tuCommand lastCommand;			// Armazena o estado atual dos sinalizadores. Veja tambem: tuCommand

// Mostra na tela o estado atual dos dois sinalizadores.
// Eh chamada SEMPRE que um dos pinos muda de valor.
static void showSignals(void) {
	char texto[80];
	sprintf(texto, "ESQUERDO: %s   |   DIREITO: %s\r\n",
		pinTurnSignal_LEFT  ? "LIGADO " : "apagado",
		pinTurnSignal_RIGHT ? "LIGADO " : "apagado");
	vPrintString(texto);
}

// Esta e a task que recebe os comandos do teclado e atualiza o valor de lastCommand
void task_Key(void *pParam){
	char tecla;

	for (;;) {
		// _kbhit() diz se existe alguma tecla esperando para ser lida
		if (_kbhit()) {
			tecla = _getch();

			if (tecla == 'l' || tecla == 'L') {
				lastCommand.TurnCommands = command_Left;	// alavanca para a esquerda
			}
			else if (tecla == 'r' || tecla == 'R') {
				lastCommand.TurnCommands = command_Right;	// alavanca para a direita
			}
			else if (tecla == ' ') {
				lastCommand.TurnCommands = command_None;	// alavanca no centro
			}
			else if (tecla == 'a' || tecla == 'A') {
				lastCommand.Alert = !lastCommand.Alert;		// liga/desliga o pisca-alerta
			}
		}
		// Espera 10 ms para nao ocupar todo o processador
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

// Inicializa a Camada de Abstracao de Hardware.
void InitHAL() {
	// Tudo comeca desligado e com a alavanca no centro
	pinTurnSignal_LEFT = FALSE;
	pinTurnSignal_RIGHT = FALSE;
	lastCommand.TurnCommands = command_None;
	lastCommand.Alert = 0;

	vPrintString("Teclas: l = esquerda | r = direita | espaco = desliga | a = pisca-alerta\r\n");
	showSignals();

	// Cria a task que le o teclado
	xTaskCreate(task_Key, "Key", configMINIMAL_STACK_SIZE, NULL, 1, NULL);
}

// Metodo que retorna o estado da  alavanca de comando dos sinalizadores ("alavanca das setas junto ao volante"). Ver tambem tuCommand
tuCommand getTurnCommand() {
	return lastCommand;
}

/* Liga ou desliga o sinalizador direito.
- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalRight(boolean s) {
	// So atualiza a tela se o valor realmente mudou
	if (pinTurnSignal_RIGHT != s) {
		pinTurnSignal_RIGHT = s;
		showSignals();
	}
}

/* Liga ou desliga o sinalizador esquerdo.
- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalLeft(boolean s) {
	if (pinTurnSignal_LEFT != s) {
		pinTurnSignal_LEFT = s;
		showSignals();
	}
}

// Inverte o estado do sinalizador direito. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalRight() {
	pinTurnSignal_RIGHT = !pinTurnSignal_RIGHT;
	showSignals();
}

// Inverte o estado do sinalizador esquerdo. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalLeft() {
	pinTurnSignal_LEFT = !pinTurnSignal_LEFT;
	showSignals();
}
