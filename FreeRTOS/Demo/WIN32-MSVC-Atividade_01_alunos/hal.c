#include "hal.h"                
#include "FreeRTOS.h"          
#include "task.h"               
#include "basic_io.h"           
#include <stdio.h>             
#include <conio.h>             

boolean pinTurnSignal_LEFT;     // Simula o pino do micro ligado a lampada ESQUERDA 
boolean pinTurnSignal_RIGHT;    // Simula o pino do micro ligado a lampada DIREITA 
tuCommand lastCommand;          // Guarda a posicao da alavanca e do botao de pisca-alerta

// Quando um pino muda de valor, mostra na tela usando essa função
static void showSignals(void) {
	char texto[80];             // cria uma string para guardar o texto que sera mostrado na tela

	// Monta o texto com o estado dos pinos
	sprintf(texto, "ESQUERDO: %s   |   DIREITO: %s\r\n", pinTurnSignal_LEFT  ? "LIGADO " : "apagado", pinTurnSignal_RIGHT ? "LIGADO " : "apagado");       
	vPrintString(texto);        // Imprime o texto montado na tela
}                       

// Recebe os comandos do teclado e atualiza o valor de lastCommand
void task_Key(void *pParam){   

	char tecla;                 // Guarda a tecla que o usuario apertou

	for (;;) {    
		if (_kbhit()) { 		// Verifica se o usuário apertudou alguma tecla    

			tecla = _getch();   // Le a tecla apertada e guarda em tecla

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
				lastCommand.Alert = !lastCommand.Alert; // Inverte o estado do alerta
			}                                            
		}

		// Espera 10 ms para nao ocupar todo o processador
		vTaskDelay(10 / portTICK_PERIOD_MS);    
	}                    
}                             

void InitHAL() {    

	// Inicializa os pinos, o comando da alavanca e o alerta como desligados
	pinTurnSignal_LEFT = FALSE; 
	pinTurnSignal_RIGHT = FALSE; 
	lastCommand.TurnCommands = command_None; 
	lastCommand.Alert = 0; 

	// Mostra na tela as instrucoes de uso do teclado e o estado inicial dos pinos
	vPrintString("Teclas: l = esquerda | r = direita | espaco = desliga | a = pisca-alerta\r\n");   
	showSignals();                         

	// Cria a task que le o teclado
	xTaskCreate(task_Key, "Key", configMINIMAL_STACK_SIZE, NULL, 1, NULL);  // Funcao, nome, pilha, parametro (nenhum), prioridade 1, handle (nao usado)
}                              

// Metodo que retorna uma struct com o estado da alavanca e do botao de pisca-alerta
tuCommand getTurnCommand() {    
	return lastCommand;         
}                             

/* Liga ou desliga o sinalizador direito.
- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalRight(boolean s) {       // Recebe TRUE para acender ou FALSE para apagar
	// So atualiza a tela se o valor realmente mudou
	if (pinTurnSignal_RIGHT != s) {     // Se o pino direito esta diferente do valor pedido...
		pinTurnSignal_RIGHT = s;        // ...grava o novo valor no pino
		showSignals();                  // ...e atualiza a tela
	}                                   // Se for igual, nao faz nada (evita linhas repetidas na tela)
}                                       // Fim de TurnSignalRight

/* Liga ou desliga o sinalizador esquerdo.
- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalLeft(boolean s) {        // Recebe TRUE para acender ou FALSE para apagar
	if (pinTurnSignal_LEFT != s) {      // Se o pino esquerdo esta diferente do valor pedido...
		pinTurnSignal_LEFT = s;         // ...grava o novo valor no pino
		showSignals();                  // ...e atualiza a tela
	}                                   // Se for igual, nao faz nada
}                                       // Fim de TurnSignalLeft

// Inverte o estado do sinalizador direito. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalRight() {                      // Nao recebe parametro: so inverte
	pinTurnSignal_RIGHT = !pinTurnSignal_RIGHT;     // O "!" troca TRUE por FALSE e FALSE por TRUE
	showSignals();                                  // Como o valor sempre muda, sempre atualiza a tela
}                                                   // Fim de ToggleTurnSignalRight

// Inverte o estado do sinalizador esquerdo. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalLeft() {                       // Nao recebe parametro: so inverte
	pinTurnSignal_LEFT = !pinTurnSignal_LEFT;       // O "!" troca TRUE por FALSE e FALSE por TRUE
	showSignals();                                  // Como o valor sempre muda, sempre atualiza a tela
}                                                   // Fim de ToggleTurnSignalLeft
