"""Live hardware measurements; no estimated or placeholder performance numbers."""
import os
import subprocess
import psutil
import torch

def hardware_status():
    process=psutil.Process(os.getpid())
    memory=psutil.virtual_memory()
    gpu=None
    if torch.cuda.is_available():
        properties=torch.cuda.get_device_properties(0)
        gpu={"name":properties.name,"vram_total_mb":round(properties.total_memory/1024**2),
             "vram_allocated_mb":round(torch.cuda.memory_allocated(0)/1024**2)}
        try:
            result=subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=2,check=True)
            utilization,used=(int(part.strip()) for part in result.stdout.splitlines()[0].split(",")[:2])
            gpu.update({"utilization_percent":utilization,"vram_system_used_mb":used})
        except (OSError,ValueError,IndexError,subprocess.SubprocessError): pass
    return {"cpu_percent":psutil.cpu_percent(interval=.1),"ram_percent":memory.percent,
        "ram_used_mb":round(memory.used/1024**2),"process_ram_mb":round(process.memory_info().rss/1024**2),
        "cuda_available":torch.cuda.is_available(),"gpu":gpu,"torch_version":torch.__version__}
