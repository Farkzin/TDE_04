#include "hal.h"                
#include "FreeRTOS.h"          
#include "task.h"               
#include "basic_io.h"           
#include <stdio.h>             
#include <conio.h>             

boolean pinTurnSignal_LEFT;     // Simula o pino do micro ligado a lampada ESQUERDA 
boolean pinTurnSignal_RIGHT;    // Simula o pino do micro ligado a lampada DIREITA 
boolean pinBrake;               // Simula o pino do micro ligado as lampadas de FREIO (dos dois lados)
tuCommand lastCommand;          // Guarda a posicao da alavanca, do pisca-alerta, da ignicao e do freio
QueueHandle_t xQueueCommand;    // Fila task_Key -> task_StateMachine

// Quando um pino muda de valor, mostra na tela usando essa função
static void showSignals(void) {
	char texto[128];            // cria uma string para guardar o texto que sera mostrado na tela

	// Se o alerta estiver ativo e as duas lâmpadas estiverem diferentes, não mostra nada ainda
	if (lastCommand.Alert && pinTurnSignal_LEFT != pinTurnSignal_RIGHT) {
		return;
	}

	// Monta o texto com o estado dos pinos
	sprintf(texto, "ESQUERDO: %s   |   DIREITO: %s   |   FREIO: %s   |   IGNICAO: %s\r\n",
		pinTurnSignal_LEFT  ? "LIGADO " : "apagado",
		pinTurnSignal_RIGHT ? "LIGADO " : "apagado",
		pinBrake            ? "LIGADO " : "apagado",
		lastCommand.Ignition ? "LIGADA " : "desligada");
	vPrintString(texto);        // Imprime o texto montado na tela
}                       

// Recebe os comandos do teclado, atualiza lastCommand e envia o comando para a fila
void task_Key(void *pParam){   

	char tecla;                 // Guarda a tecla que o usuario apertou

	for (;;) {    
		if (_kbhit()) { 		// Verifica se o usuário apertudou alguma tecla    

			tecla = _getch();   // Le a tecla apertada e guarda em tecla

			switch (tecla) {
				case 'l': case 'L': lastCommand.TurnCommands = command_Left;        break;
				case 'r': case 'R': lastCommand.TurnCommands = command_Right;       break;
				case ' ':           lastCommand.TurnCommands = command_None;        break;
				case 'a': case 'A': lastCommand.Alert    = !lastCommand.Alert;      break; // Inverte o estado do alerta
				case 'i': case 'I': lastCommand.Ignition = !lastCommand.Ignition; showSignals(); break; // Inverte a ignicao e mostra na tela
				case 'b': case 'B': lastCommand.Brake    = !lastCommand.Brake;      break; // Inverte o freio
				default: continue; // Tecla invalida: nao envia nada para a fila
			}

			// Envia uma copia do comando atual para a fila, acordando a task_StateMachine
			xQueueSend(xQueueCommand, &lastCommand, 0);
		}

		// Espera 10 ms para as outras tasks do FreeRTOS serem executadas
		vTaskDelay(10);    
	}                    
}                             

void InitHAL() {    

	// Inicializa os pinos, o comando da alavanca, o alerta, a ignicao e o freio como desligados
	pinTurnSignal_LEFT = FALSE; 
	pinTurnSignal_RIGHT = FALSE; 
	pinBrake = FALSE;
	lastCommand.TurnCommands = command_None; 
	lastCommand.Alert = 0; 
	lastCommand.Ignition = 0;
	lastCommand.Brake = 0;

	// Cria a fila com espaco para 10 comandos (folga caso o usuario aperte varias teclas rapido)
	xQueueCommand = xQueueCreate(10, sizeof(tuCommand));

	// Mostra na tela as instrucoes de uso do teclado e o estado inicial dos pinos
	vPrintString("Teclas: l = esquerda | r = direita | espaco = desliga | a = pisca-alerta | i = ignicao | b = freio\r\n");   
	showSignals();                         

	// Cria a task que le o teclado
	xTaskCreate(task_Key, "Key", configMINIMAL_STACK_SIZE, NULL, 3, NULL);  // Funcao, nome, pilha, parametro (nenhum), prioridade 3, handle (nao usado)
}                              

// Função que liga ou desliga o sinalizador direito
void TurnSignalRight(boolean s) {      
	if (pinTurnSignal_RIGHT != s) { // Se o pino direito esta diferente do valor pedido, atualiza o valor e a tela
		pinTurnSignal_RIGHT = s;        
		showSignals();                  
	}                                   
}                                  

// Função que liga ou desliga o sinalizador esquerdo
void TurnSignalLeft(boolean s) {        
	if (pinTurnSignal_LEFT != s) { // Se o pino esquerdo esta diferente do valor pedido, atualiza o valor e a tela
		pinTurnSignal_LEFT = s;         
		showSignals();                  
	}                                   
}                                       

// Inverte o estado do sinalizador direito e atualiza a tela
void ToggleTurnSignalRight() {                 
	pinTurnSignal_RIGHT = !pinTurnSignal_RIGHT;
	showSignals();                             
}                                              

// Inverte o estado do sinalizador esquerdo e atualiza a tela
void ToggleTurnSignalLeft() {                       
	pinTurnSignal_LEFT = !pinTurnSignal_LEFT;       
	showSignals();                                  
}                                                   

// Função que liga ou desliga a luz de freio
void BrakeLight(boolean s) {
	if (pinBrake != s) { // Se o pino do freio esta diferente do valor pedido, atualiza o valor e a tela
		pinBrake = s;
		showSignals();
	}
}
