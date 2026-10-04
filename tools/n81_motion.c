// SPDX-License-Identifier: GPL-3.0-or-later
/* Fix this process's writable CoreMotion model cache only.
 * No executable-page patch, remote-task write, system file or boot change.
 * The signed CoreMotion image must match the inspected 11D257 UUID and getter.
 */
extern void *dlopen(const char *,int);
extern void *dlsym(void *,const char *);
extern int printf(const char *,...);
typedef unsigned int U;
int touch4_motion_apply(void) {
    void *lib=dlopen("/usr/lib/libSystem.B.dylib",2);
    int (*sysctlname)(const char*,void*,U*,void*,U)=dlsym(lib,"sysctlbyname");
    int (*eq)(const char*,const char*)=dlsym(lib,"strcmp");
    int (*equalbytes)(const void*,const void*,U)=dlsym(lib,"memcmp");
    U (*count)(void)=dlsym(lib,"_dyld_image_count");
    const char*(*name)(U)=dlsym(lib,"_dyld_get_image_name");
    const U*(*header)(U)=dlsym(lib,"_dyld_get_image_header");
    if(!sysctlname||!eq||!equalbytes||!count||!name||!header)return -1;
    char machine[64]={0},board[64]={0};U n=sizeof(machine),b=sizeof(board);
    if(sysctlname("hw.machine",machine,&n,0,0)||sysctlname("hw.model",board,&b,0,0))return -2;
    machine[63]=board[63]=0;
    if(eq(machine,"iPod4,1")||eq(board,"N81AP"))return -3;
    dlopen("/System/Library/Frameworks/CoreMotion.framework/CoreMotion",2);
    for(U i=0;i<count();i++)if(!eq(name(i),"/System/Library/Frameworks/CoreMotion.framework/CoreMotion")) {
        const U *h=header(i);
        if(h[0]!=0xfeedface||h[1]!=12||h[4]>100||h[5]>16384)return -4;
        const unsigned char wanted[]={0xf5,0x41,0x18,0x35,0x64,0x87,0x3c,0x84,0x89,0xcc,0xe9,0xde,0xca,0x3e,0x9b,0xd5};
        const U *command=h+7;U offset=0;int uuidok=0;
        for(U j=0;j<h[4];j++) {
            if(offset+8>h[5]||command[1]<8||offset+command[1]>h[5])return -5;
            if(command[0]==0x1b && command[1]==24 && !equalbytes(command+2,wanted,16))uuidok=1;
            offset+=command[1];command=(const U*)((const unsigned char*)command+command[1]);
        }
        if(!uuidok)return -6;
        U slide=(U)h-0x2da1d000;
        const unsigned char original[]={0xf0,0xb5,0x41,0xf6,0x40,0x16,0x03,0xaf,0xc0,0xf6,0xa2,0x26,0x7e,0x44,0x70,0x68};
        if(equalbytes((void*)(slide+0x2da34e80),original,sizeof(original)))return -7;
        int (*getter)(void)=(void*)((slide+0x2da34e80)|1);
        int *cache=(void*)(slide+0x384567d4);
        int previous=getter();
        if(previous==11 && *cache==11)return 0;
        if(previous!=0 || *cache!=0)return -8;
        *cache=11;
        if(getter()!=11){*cache=previous;return -9;}
        printf("N81-MOTION applied process-local model=%d\n",*cache);
        return 1;
    }
    return -10;
}
__attribute__((constructor)) static void init(void) {
    int status=touch4_motion_apply();
    printf("N81-MOTION status=%d\n",status);
    void *lib=dlopen("/usr/lib/libSystem.B.dylib",2);
    int (*flush)(void*)=dlsym(lib,"fflush");
    if(flush)flush(0);
}
