// SPDX-License-Identifier: GPL-3.0-or-later
/* Experimental N81-only VirtualAudio routing repair. No shared cache or kernel writes. */
extern void *dlopen(const char*,int);
extern void *dlsym(void*,const char*);
typedef unsigned int U;
int touch4_audio_route_apply(void){
 void *lib=dlopen("/usr/lib/libSystem.B.dylib",2);
 int(*sysctlname)(const char*,void*,U*,void*,U)=dlsym(lib,"sysctlbyname");
 int(*eq)(const char*,const char*)=dlsym(lib,"strcmp");int(*same)(const void*,const void*,U)=dlsym(lib,"memcmp");
 U(*count)(void)=dlsym(lib,"_dyld_image_count");const char*(*name)(U)=dlsym(lib,"_dyld_get_image_name");const U*(*header)(U)=dlsym(lib,"_dyld_get_image_header");
 if(!sysctlname||!eq||!same||!count||!name||!header)return -1;
 char machine[64]={0},board[64]={0};U n=sizeof(machine),b=sizeof(board);
 if(sysctlname("hw.machine",machine,&n,0,0)||sysctlname("hw.model",board,&b,0,0))return -2;
 machine[63]=board[63]=0;if(eq(machine,"iPod4,1")||eq(board,"N81AP"))return -3;
 const unsigned char wanted[]={0xd6,0x7d,0x8d,0x29,0x7b,0xb8,0x36,0xfa,0xae,0x23,0x1b,0x0b,0x45,0x8c,0xbe,0x98};
 for(U i=0;i<count();i++)if(!eq(name(i),"/Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin/VirtualAudio")){
  const U*h=header(i);if(h[0]!=0xfeedface||h[1]!=12||h[4]>100||h[5]>16384)return -4;
  const U*c=h+7;U offset=0;int uuidok=0,cachewritable=0;
  for(U j=0;j<h[4];j++){
   if(offset+8>h[5]||c[1]<8||offset+c[1]>h[5])return -5;
   if(c[0]==0x1b&&c[1]==24&&!same(c+2,wanted,16))uuidok=1;
   if(c[0]==1&&c[1]>=56&&c[6]<=0x2adf88&&c[6]+c[7]>=0x2adf8c&&(c[11]&2))cachewritable=1;
   offset+=c[1];c=(const U*)((const unsigned char*)c+c[1]);
  }
  if(!uuidok||!cachewritable)return -6;
  U slide=(U)h;
  const unsigned char original[]={0x80,0xb5,0x48,0xf2,0xe8,0x70,0x6f,0x46,0xc0,0xf2,0x29,0x00,0x78,0x44,0x01,0x78};
  if(same((void*)(slide+0x15778),original,sizeof(original)))return -7;
  int(*getter)(void)=(void*)((slide+0x15778)|1);int*cache=(void*)(slide+0x2adf88);int previous=getter();
  if(previous==16&&*cache==16)return 0;
  if(previous!=0||*cache!=0)return -8;
  /* K93 supplies an existing single-microphone routing profile. The IOAudio2
   * CS42L59 driver and N81 tuning directory remain unchanged. Broader audio
   * routes and gain behavior need device testing before this becomes a release. */
  *cache=16;if(getter()!=16){*cache=previous;return -9;}return 1;
 }
 return -10;
}
__attribute__((constructor))static void init(void){int status=touch4_audio_route_apply();void*l=dlopen("/usr/lib/libSystem.B.dylib",2);void(*log)(int,const char*,...)=dlsym(l,"syslog");if(log)log(5,"N81-AUDIO routing status=%d",status);}
