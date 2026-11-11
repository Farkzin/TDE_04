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
