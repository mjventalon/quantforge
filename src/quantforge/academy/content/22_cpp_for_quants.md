---
id: 22
level: 7
level_name: Quant Programming
title: C++ for quants — types, loops, vectors and compiling
minutes: 45
objectives:
  - Explain why banks and trading firms write pricing and risk engines in C++
  - Read and write C++ functions with types, loops, std::vector and const references
  - Compile a program, read compiler errors and run it
widgets: [engine_benchmark]
sources:
  - title: "6.096 Introduction to C++ (January IAP 2011)"
    by: "MIT OpenCourseWare (Jesse Dunietz, Geza Kovacs, John Marrero)"
    url: "https://ocw.mit.edu/courses/6-096-introduction-to-c-january-iap-2011/"
  - title: "6.S096 Introduction to C and C++ (January IAP 2013)"
    by: "MIT OpenCourseWare (Tom Lieber, Kyle Murray, Frank Li)"
    url: "https://ocw.mit.edu/courses/6-s096-introduction-to-c-and-c-january-iap-2013/"
  - title: "Get Started! — Standard C++"
    by: "Standard C++ Foundation (isocpp.org)"
    url: "https://isocpp.org/get-started"
  - title: "C++ reference"
    by: "cppreference.com"
    url: "https://en.cppreference.com/w/cpp"
  - title: "A Tour of C++, 3rd ed. (2022)"
    by: "Bjarne Stroustrup (book)"
    url: ""
quiz:
  - q: "Why are many pricing and risk engines written in C++?"
    options: ["C++ is the only language banks may use", "Compiled C++ is very fast and gives precise control over memory", "C++ has no bugs", "It needs no compiler"]
    answer: 1
    why: "Speed and predictable performance matter when you revalue millions of positions."
  - q: "In C++, `double x = 0.05;` means:"
    options: ["x can later hold text", "x is a 64-bit floating-point number", "x is an integer", "x is constant"]
    answer: 1
    why: "C++ is statically typed: every variable has a fixed type checked at compile time."
  - q: "What does `const std::vector<double>& x` in a function signature give you?"
    options: ["A copy of the vector", "Access to the caller's vector without copying it and without modifying it", "A vector of constants only", "A pointer that may be null"]
    answer: 1
    why: "A const reference avoids an expensive copy and promises not to change the data."
  - q: "What does the compiler do?"
    options: ["Runs your code line by line", "Translates the whole program into machine code before it runs", "Downloads libraries", "Formats your code"]
    answer: 1
    why: "Errors in types or syntax are therefore caught before the program ever runs."
  - q: "`for (int i = 0; i < n; ++i)` runs the loop body:"
    options: ["n + 1 times", "n times, with i = 0 … n − 1", "Forever", "Once"]
    answer: 1
    why: "Start at 0, stop before n, add one each time."
  - q: "Integer division: what is `7 / 2` in C++ when both are int?"
    options: ["3.5", "3", "4", "A compile error"]
    answer: 1
    why: "int / int truncates. Write 7.0 / 2 to get 3.5 — a classic bug in financial code."
---

## Why C++?

Python is perfect for research: you try an idea in minutes. But when a bank must revalue **every
trade, under thousands of scenarios, every night**, or a market maker reprices options thousands of
times per second, interpreter overhead becomes unacceptable. C++ is **compiled** to machine code,
lets you control memory precisely and, used well, runs close to the hardware's limits. That is why
pricing libraries, risk engines and trading systems are typically written in C++, with Python on
top for research and scripting.

quantforge itself does this: its **C++ engine** (`src/quantforge/native/cpp`) prices options in
C++, uses every CPU core for Monte-Carlo, and is called from Python. The benchmark below runs on
*your* machine if the engine is built.

{{widget:engine_benchmark}}

## 1. A first program

```cpp
#include <cstdio>
#include <cmath>

double future_value(double pv, double rate, int years) {
    return pv * std::pow(1.0 + rate, years);
}

int main() {
    std::printf("%.2f\n", future_value(1000.0, 0.05, 10));   // 1628.89
    return 0;
}
```

* `#include` brings in a part of the standard library (`<cmath>` for `std::exp`, `std::log`…).
* Every variable and function has a **type**: `double` (real number), `int` (integer), `bool`.
* Every program starts in `main`. Statements end with `;`, blocks use `{ }`.

Compile and run (macOS: install the compiler once with `xcode-select --install`):

```bash
c++ -std=c++17 -O2 first.cpp -o first
./first
```

`-O2` asks the compiler to optimise. If you make a mistake, the compiler stops and tells you the
**file, line and reason** — read the *first* error first; the others are often consequences.

## 2. Loops and conditions

```cpp
double value = 1.0;
int years = 0;
while (value < 2.0) {          // how long to double at 7%?
    value *= 1.07;
    ++years;
}
for (int i = 0; i < 10; ++i) { /* runs 10 times, i = 0..9 */ }
if (value > 2.0) { /* ... */ } else { /* ... */ }
```

## 3. `std::vector`: the C++ array

```cpp
#include <vector>
std::vector<double> prices = {100.0, 101.5, 99.8};
prices.push_back(102.3);                 // add an element
double first = prices[0];                // index from 0
for (double p : prices) { /* range-for: each element */ }
```

Pass large data **by const reference** to avoid copying it:

```cpp
double mean(const std::vector<double>& x) {
    double s = 0.0;
    for (double v : x) s += v;
    return s / x.size();
}
```

## 4. Three classic bugs in financial C++

1. **Integer division** — `int years = 7; double half = years / 2;` gives 3, not 3.5. Write `years / 2.0`.
2. **Off-by-one** — a tree with `n` steps has `n + 1` terminal nodes.
3. **Uninitialised variables** — `double sum;` contains garbage. Always write `double sum = 0.0;`.

## Your turn

Rewrite the functions below in C++. When you run quantforge on your own computer the grader
compiles and tests your code; on the public website you can download a ready-to-compile file with
the tests included.
