# attack lab target12 - report

- 姓名：吴卓阳
- 学号：23307130392
- 日期：2024.11.5



## Phase 1

​	目标：主函数调用`test()`，`test()`调用`getbuf()`，此时栈中记录了返回地址并按`gutbuf()`需要分配好空间，需设计字符串输入，使得输入超出`getbuf()`预分配的栈空间，超出部分为函数`touch1`的地址，执行完`getbuf()`后便会进入`touch1`

​	反汇编查看三个函数：

![image-20241030120715629](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241030120715629.png)

​	首先对于`getbuf()`，栈指针后退了24，说明栈上此时需要输入24个Byte，超出部分则会覆盖函数的返回地址。再根据`hex2raw`的功能，可以将16进制转换为2进制字符串，因此需要构建输入：前24个Byte为任意16进制数，需要48位16进制数来填满应该有的输入，；最后8个Byte为函数`touch1`的入口地址。

​	然后对于`touch1`，函数首地址为0x0000000000402618，此为应该被覆盖到返回地址上的内容。

​	其次，由于机器采用小端序，实际输入时是从低地址开始写入，因此低位字节应该先写入，实际输入应该为 18 26 40 00 00 00 00 00，可以构建出注入字符串，储存在phase1.txt中：

![image-20241030130649004](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241030130649004.png)

​	通过指令运行后，触发`touch1`:

![image-20241030130718796](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241030130718796.png)



## Phase 2

​	目标：仍旧使用`getbuf()`读取,需要通过输入实现栈溢出覆盖返回地址，将函数引向注入代码，在注入代码中修改传入touch2的参数，使其和cookie相等，并且通过`ret`继续操控跳转方向回到touch2：

![image-20241104203559194](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104203559194.png)

​	查看`touch2`的汇编代码可以得知，`cookie`储存在`0x4fae84`中，为`0x50fa73aa`，我们需要在注入代码中将此地址中的值传入`%rdi`中。

​	同时，我们需要找到在栈中注入代码的起始地址。根据`getbuf`函数，我们得知这个地址储存在`%rsp`中，因此通过打断点和查询寄存器中的值，我们得到函数开始地址：

![image-20241104214648082](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104214648082.png)

​	从而可以编写`phase2.s`，通过指令将其汇编后再反汇编，可以得到机器码：

![image-20241104214802596](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104214802596.png)

![image-20241104214748232](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104214748232.png)

​	构建输入`phase2.txt`如下：

![image-20241104214834118](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104214834118.png)

​	先输入注入代码，通过任意16进制数填满输入后，将返回地址覆盖为注入代码地址，实现功能，运行成功结果如下：

![image-20241104215047262](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104215047262.png)



## Phase3

​	仍旧需要通过输入溢出覆盖函数返回地址使其进入`touch3`，并且将函数`hexmatch`的返回值设为1。

​	根据函数的源码我们可以得知，`hexmatch`函数会将输入的8位16进制数转换为字符串，随机存储在`cbuf`中，将字符串的起始地址记为`s`，与输入地址`sval`中长度为9的字符串进行比较，需要满足两串字符串一致。

​	先查看`touch3`函数

![image-20241104222852423](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104222852423.png)

​	将`cookie`作为函数`hexmatch`的第一个参数，已知为`0x50fa73aa`，转换为ascii码的16进制后为`0x 35 30 66 61 37 33 61 61`,随后调用`hexmatch`，查看函数：

![image-20241104223711969](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104223711969.png)

![image-20241104223729074](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241104223729074.png)

​	可知函数再`getbuf`之后又分配了136字节空间，对字符串进行随机存储。我们不能贸然将已知字符串存进这些空间中，以免出现覆盖，因此，我们选择通过溢出，在`test`栈区进行`cookie`的存储。我们已经得知，调用函数`getbuf`之后，栈顶指针`%rsp = 0x55617478`，我们将其向上增加24个字节后来到`0x55617490`，这是返回地址的存储位置，我们需要将其设为`touch3`的首地址；再向上增加8个字节后进入`test`栈区`0x55617498`，由于我们不再返回`test`，因此可以随意利用，从而设计注入代码：

![image-20241105010037555](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105010037555.png)

​	进行汇编和反汇编后得到机器码：

![image-20241105010102079](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105010102079.png)

​	由此可以构建输入，由注入代码、补足位数的任意输入、注入代码首地址（`getbuf`的栈顶指针）、`touch3`首地址以及`cookie`组成，将`cookie`写入到`0x55617498`中：

![image-20241105010236923](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105010236923.png)

​	测试结果如下：

![image-20241105010345556](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105010345556.png)



## Phase4

​	由于堆栈位置的随机化，我们无法确定注入代码的位置，因此我们需要利用现有的代码来实现功能。

​	根据Phase2的要求，我们可以得知，我们需要使函数在执行`getbuf`之后进入注入代码段，完成对`%rdi`的赋值，再执行`touch3`，因此我们可以先写出一段注入代码的逻辑：首先需要`pop`出`cookie`的值，再将其值传入`%rdi`，我们需要通过`retq`来调整函数的运行位置。

​	因此，查表，首先寻找含有`pop`指令的函数，为`58`，后面只能有`90 c3`：

![image-20241105123707919](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105123707919.png)

​	对应`popq %rax`，查看其地址为`0x402847`。

![image-20241105123727788](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105123727788.png)

​	再寻找`movq %rax,%rdi`，查表为`48 89 c7 c3`，寻找函数：

![image-20241105121920442](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105121920442.png)

​	查看地址为`0x402869`：

![image-20241105122015014](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105122015014.png)

​	因此可以构建phase4.txt为：

![image-20241105124547542](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105124547542.png)

​	其中，首先构建24个字节的无意义输入填满空间，将返回地址覆盖为`pop`指令的地址，将`cookie`值填充到栈上作为`pop`进`%rax`的值，再填充上`movq`指令的地址，当`pop`指令弹出`cookie`值后执行`retq`时，就会进入到`movq`指令中，最后将`touch3`首地址填充进去，这样`movq`在返回时执行`retq`，程序进入`touch3`，执行结果如下：

![image-20241105125408938](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105125408938.png)



## Phase5

​	先确定基础思路，由于有栈随机性，所以我们无法确定`cookie`的具体存储位置，但是我们只能在栈中存储`cookie`，因此可以通过栈顶指针+偏移量的方式来计算`cookie`的位置，因此先查找有关`%rsp`的指令代码：

![image-20241105131719786](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105131719786.png)

​	发现`48 49 e0 c3`，说明`movq %rsp,%rax`可用，又由phase4得知`movq %rax,%rdi`可用，所以是将`%rsp`放进`%rax`，再放进`%rdi`中，此时`%rdi`中存储的为栈顶指针，我们注意到有函数：

![image-20241105132914316](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105132914316.png)

​	这里利用`%rsi`作为索引来对栈中元素进行查找，并储存在`%rax`中，可以推测索引到`cookie`，并且将它的地址放到了`%rax`中，接下来还需要一步`movq %rax,%rdi`将地址传入参数之中。通过上述推断，我们开始寻找代码地址：

![image-20241105142529257](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105142529257.png)

​	则`movq %rsp,%rax`的地址为`0x4028bc`。

![image-20241105142647770](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105142647770.png)

​	则索引功能代码地址为：`0x402888`。

​	由phase3中已知`movq %rax,%rdi`地址为地址为`0x402869`。

​	因此可以构造phase5.txt：

![image-20241105144444109](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105144444109.png)

​	首先，用24字节的任意输入填充栈区，随后将函数返回地址覆盖为`movq %rsp,%rax`的地址，再将后面的地址设置为利用`%rsi`索引栈区，将值赋给`%rax`的函数功能的地址，再次入栈`movq %rsp,%rax`的地址，最后入栈`touch3`的地址，随后根据题目中的描述，原答案中使用了8个`gadget`，而这里只使用了4个，所以需要以任意输入补齐剩余位数，最后输入将`cookie`的ascii码的16进制表示作为参数。

​	这样，在每行注入代码完毕`retq`时，都会从栈中退出下一步代码的地址并继续执行相应注入代码，直到我们注入的代码全部执行完毕后进入`touch3`，此时传入参数已经更改为想要的值，执行结果如下：

![image-20241105144502308](C:\Users\wzy\AppData\Roaming\Typora\typora-user-images\image-20241105144502308.png)
