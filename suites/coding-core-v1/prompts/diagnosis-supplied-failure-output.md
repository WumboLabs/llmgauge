# Supplied failure-output diagnosis

## Task

Diagnose the supplied compiler failure without proposing a code repair. Separate observed facts, likely cause, uncertainty, and discriminating next checks.

## Supplied inert context

All output and source excerpts below are prompt-owned text. No compiler or repository is available.

Producer facts:

- Compiler: `rustc 1.77.2 (25ef9e3d8 2024-04-09)`.
- Command that produced the output: `cargo check --locked`.
- The command exited with status `101`.
- The excerpt includes the complete diagnostic for this failure; it is not truncated.
- Dependency versions are fixed by an inert lockfile, but dependency source and documentation are not supplied.

Relevant source excerpt:

```rust
fn launch(tx: Sender<Event>, worker: Worker) -> JoinHandle<()> {
    std::thread::spawn(move || {
        worker.run(tx);
    })
}

fn supervise(tx: Sender<Event>, worker: Worker) {
    let handle = launch(tx, worker);
    drop(tx);
    handle.join().expect("worker panicked");
}
```

Complete compiler output:

```text
error[E0382]: use of moved value: `tx`
  --> src/supervisor.rs:19:10
   |
17 | fn supervise(tx: Sender<Event>, worker: Worker) {
   |              -- move occurs because `tx` has type `Sender<Event>`, which does not implement the `Copy` trait
18 |     let handle = launch(tx, worker);
   |                         -- value moved here
19 |     drop(tx);
   |          ^^ value used here after move
   |
note: consider changing this parameter type in function `launch` to borrow instead if owning the value isn't necessary
  --> src/supervisor.rs:11:15
   |
11 | fn launch(tx: Sender<Event>, worker: Worker) -> JoinHandle<()> {
   |    ------     ^^^^^^^^^^^^^ this parameter takes ownership of the value
   |    |
   |    in this function

For more information about this error, try `rustc --explain E0382`.
error: could not compile `relay` (lib) due to 1 previous error
```

Unknown facts:

- `Worker::run`'s signature and whether it must own a sender are not supplied.
- The intended channel-shutdown timing is not supplied.
- No runtime behavior is observable because compilation failed.

Do not use current external Rust knowledge as evidence beyond what the supplied diagnostic states. Do not rewrite the function, provide patch text, or claim a command was run.

## Response form

Use `coding-core-explanation-only-form-v0` `0.1.0`. Return prose under exactly these four headings, in order: `Observed facts`, `Likely cause`, `Uncertainty`, and `Discriminating next checks`. Inline identifiers and quoted command recommendations are allowed; fenced code blocks and repair code are not.

Any recommended checks are response text only and will not be executed.
