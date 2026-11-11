#ifndef DATATYPES_H
#define DATATYPES_H

//Macro de compilacao para Win32 (Windows 2000/XP/Vista/7/8 and Windows Server 2003/2008)
#ifdef  _WIN32
    typedef char                int8;
    typedef short               int16;
    typedef int                 int32;
    typedef unsigned char       uint8;
    typedef unsigned short      uint16;
    typedef unsigned int        uint32;
#endif

//Macro de compilacao para Keil C51
#ifdef  __C51__
    typedef char                int8;
    typedef int                 int16;
    typedef long                int32;
    typedef unsigned char       uint8;
    typedef unsigned int        uint16;
    typedef unsigned long       uint32;
#endif

//Macro de compilacao para RENESAS
#ifdef  __RENESAS__
    typedef char                int8;
    typedef short               int16;
    typedef int                 int32;
    typedef unsigned char       uint8;
    typedef unsigned short      uint16;
    typedef unsigned int        uint32;
#endif

typedef uint8     boolean;

//Definicoes de Verdadeiro e Falso
#define TRUE        1
#define FALSE       0

#endif // DATATYPES_H
